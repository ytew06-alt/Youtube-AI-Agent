# AI Agent — Pre-Publish Checklist

Everything standing between the current build and a VS Code Marketplace release.
Ordered by severity, not by effort.

---

## 1. Ship Blockers

These aren't polish. The extension either doesn't run on someone else's machine, or it's unsafe when it does.

- **Hardcoded auth token** — `LOCAL_TOKEN = "hidden_dev_token"` appears in both `extension.ts` and `server.py`. Once published, that string is public, and the backend accepts *any* connection presenting it. Generate a random token per session in `activate()`.
- **Pass the token via environment, not argv** — process arguments are visible to other users in the process list. Use the `env` option on `spawn`, and read it with `os.environ` in `server.py`.
- **Backend path won't survive packaging** — `path.join(context.extensionPath, '..')` only works because the extension folder currently sits inside your repo. A packaged `.vsix` has no parent directory containing `server.py`. Move the Python code *inside* the extension folder.
- **`uv` is assumed to be on PATH** — most users don't have it. Detect it, and fail with a message that says exactly what to install rather than a raw spawn error.
- **Port 8000 is hardcoded** — collides with every other dev server, and if something else already owns it your extension will cheerfully connect to *that instead*. Bind port `0`, let the OS assign, and parse the real port from uvicorn's stdout in your existing `outputChannel` handler.

> **Prototype packaging first.** Shipping a Python backend inside a VS Code extension is one of the harder distribution problems in the ecosystem. Find out early whether your chosen approach is workable.

---

## 2. Security

- **`run_python_file` executes arbitrary model-generated code** with no sandbox — the single biggest risk in the project. Require explicit user consent on first use per session, and disclose it prominently in the README. This is the kind of thing that gets an extension pulled.
- **Add an `Origin` check** on the websocket handshake, alongside the token. Defence in depth against a local page connecting to your server.
- **State files land in the wrong place** — `history.json`, `cache.json`, and `gemini_usage.json` are written to the backend's cwd (your extension directory). Use `context.globalStorageUri`.
- **History isn't scoped per workspace** — opening project B silently inherits project A's conversation. Key history by workspace path.
- **Kill the whole process tree on deactivate** — `backendProcess.kill()` kills `uv`, not necessarily the uvicorn child. Orphaned servers holding your port are a bad first impression.
- **`run_python_file` invokes `"python"`** — that's `python3` on most macOS and Linux setups.
- **Path-traversal guards are security-critical** — the `commonpath` checks in `get_file_content`, `write_file`, and `run_python_file` are your entire sandbox. Treat them accordingly (see Testing).

---

## 3. Outstanding Code Fixes

Known issues already identified but not yet resolved.

- **`extract_from_youtube.py` still needs its edits** — import `VIDEO_MODEL` and `call_with_fallback`, set `model=VIDEO_MODEL` in *both* `process_chunk` and `merge_chunks`, unpack the chunk tuple (`for i, (start, end) in enumerate(chunks)`), and move the single-chunk `return` outside the loop.
- **`generate_key` computes `prefix` and never uses it** — the returned key is `f"{function_name}:{json_args}"`, with no prefix. This means `cache.invalid_multiple_keys(file_path)` may not match the keys you think it does, which would serve stale file contents after a write. **Read `cache.py` and confirm.**
- **`generate_key` mutates its input** — `args["file_path"] = os.path.normpath(...)` writes back into `function_call.args`.
- **`get_files_info` is missing a newline** — entries concatenate onto one line, which degrades model comprehension and costs you extra tool calls.
- **Bare `except:` blocks** in `get_file_content` and `write_file` return `"Error:"` with no detail, making every failure look identical.
- **Wrap usage-accounting in try/except** — a stats line should never be able to destroy an expensive API result via rollback.
- **`main()` calls `Agent("./calculator")`** with no `api_key` — will raise. Affects the CLI path only.
- **`ai-agent.helloWorld`** is declared in `contributes.commands` but never registered — it shows in the palette and errors when invoked.

---

## 4. Frontend & UX

What decides whether people keep the extension installed.

- **Markdown / code-block rendering** — currently `bubble.textContent = text`, so code arrives as an unformatted wall. Use `markdown-it` with `html: false`.
- **Watch for XSS when you switch** — the moment you reach for `innerHTML`, model output becomes an injection vector, and that output can originate from a YouTube video you don't control. Keep the existing nonce CSP. Don't hand-roll the parser.
- **Cancel button** — there is currently no way to stop a running task, and with retries plus the fallback chain a stuck turn can hang for minutes.
- **Diff before writing files** — the single biggest trust feature you can add. Nobody wants an agent silently overwriting their code.
- **Surface remaining quota** — wire up `budget_report()`. Free-tier users will hit their daily limit on day one and assume the extension is broken.
- **Stream responses** rather than waiting for a single `DONE:` message.
- **Persist chat across panel close** — `getState` / `setState`.
- **Fix the duplicated connection error** — the "Backend not running" `postMessage` sits outside the inner `if/else`, so it fires on every retry attempt.
- **Reset `retryAttempts = 0`** inside `socket.on('open')`, or a later disconnect starts counting from wherever it left off and gives up early.

---

## 5. Testing

Prioritise tests that need no API access — they're the fastest, the most stable, and they double as the best way to learn your own codebase.

- **Path-traversal guards** — feed `../../etc/passwd`, absolute paths, and symlinks to all three file functions. Pure functions, security-critical, trivially testable.
- **`get_chunks` boundary math** — the overlap logic around `CHUNK_THRESHOLD`, and a duration of exactly `900`.
- **`classify()` against saved error payloads** — you've now seen real 429 and 503 responses. Save them as fixtures.
- **`RateLimiter` pacing and the day rollover** — including the Pacific-midnight boundary.
- **Mock the Gemini client** so the suite never spends quota.
- **Cache invalidation after `write_file`** — directly tests the `generate_key` question above.

---

## 6. Marketplace Requirements

- **`publisher` field in `package.json`** — required; publishing fails without it.
- `repository`, `license`, `icon`, `keywords`, and a real `description`.
- **`README.md`** — this *is* your marketplace page. Screenshots or a GIF matter more than prose.
- `CHANGELOG.md` and a `LICENSE` file.
- **`.vscodeignore` + esbuild bundling** — otherwise `node_modules` ships inside the vsix.
- **Lower `engines.vscode`** — `^1.125.0` is very recent and needlessly narrows your audience unless you depend on something specific.
- **Test with `vsce package`** and install the `.vsix` locally before publishing.

---

## 7. Dependency Hygiene

- **Unpin `google-genai`** — `uv add "google-genai>=2.8.0,<3"` (this also updates `uv.lock`; hand-editing the TOML requires a follow-up `uv lock`).
- **The 2.x AFC breaking change doesn't affect you** — you use explicit `function_declarations` and handle `response.function_calls` yourself, which is manual function calling.
- **Remove `python-dotenv`** if unused — the API key now arrives over the websocket.
- **Prefer `>=x,<next-major` over `==`** — hard pins on a fast-moving SDK are how you end up sixty versions behind without noticing.
- **Verify `MODEL_LIMITS`** in `models.py` against your own dashboard. The Flash-Lite numbers are a guess.
- **Never use `-latest` aliases** — an alias that silently re-points also silently changes which quota bucket you spend from.

---

## 8. Suggested v0.1 Scope

You don't need all of the above to publish. A defensible preview release is:

1. Session token
2. Packaging path
3. Dynamic port
4. Consent prompt on `run_python_file`
5. Path-traversal tests
6. README + marketplace metadata

Ship that, then let real users tell you whether they want streaming before you build streaming.

---

## 9. Learning the Codebase

Four exercises, in order. These will teach you more than the next fifty hours of feature work.

- **Draw the request lifecycle from memory** — keypress → `postMessage` → extension host → websocket frame → FastAPI → `run_in_executor` → `Agent.chat` → rate limiter → Gemini → tool call → `types.Content` → back up. On paper, without opening the files. **Every place you stall is a gap.** Then open the files and correct it.
- **Write the tests** — you can't test `get_chunks` without understanding the overlap math, or `classify()` without understanding Google's error envelope. Testing forces you to state each contract precisely, which is exactly the knowledge you're after.
- **Do a "what breaks if I delete this" pass** — one sentence per file. Anywhere you can't answer crisply is where to read next.
- **Write `ARCHITECTURE.md`** — not for users, for you. If you can explain the system in two pages, you know it. Bonus: it's 80% of your README.

**Likely weak spots**, based on the code: the `run_in_executor` threading model in `server.py`, webview ↔ extension-host message passing, and thought signatures.
