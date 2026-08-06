"""
WebSocket backend for the AI Agent VS Code extension.

Why the structure looks like this:
  - The agent runs in a worker thread (run_in_executor) because it is blocking,
    synchronous code. While it runs, the event loop must STILL be reading the
    socket - otherwise an approval reply from the webview would never arrive.
  - So reading is split into a background `reader` task that dispatches by
    message type, and the main loop pulls prompts off a queue instead of
    reading the socket itself. Only one coroutine may ever call receive_text().
  - Approvals cross the thread boundary via concurrent.futures.Future, which is
    safe to block a worker thread on. asyncio.Future is NOT.
"""

import asyncio
import importlib.metadata
import json
import os
import re
import secrets
import traceback
import uuid
from concurrent.futures import Future
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from agent_class import Agent
import threading
from config import CancelledByUser
from gemini_client import budget_report

MAX_PROMPT_LENGTH = 4000
APPROVAL_TIMEOUT = 300          # seconds a pending approval waits before denying
SEND_TIMEOUT = 10               # seconds to get the ASK onto the wire

# Fail fast rather than falling back to a default. A default token is exactly
# the bug this replaced.
EXPECTED_TOKEN = os.environ.get("AI_AGENT_TOKEN")
if not EXPECTED_TOKEN:
    raise RuntimeError("AI_AGENT_TOKEN not set - refusing to start")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # on_event("startup") is deprecated; lifespan is the supported replacement.
    print("google-genai version in use:", importlib.metadata.version("google-genai"))
    print("AI Agent backend starting")
    yield
    print("AI Agent backend shutting down")


app = FastAPI(lifespan=lifespan)


@app.websocket("/chat")
async def chat_endpoint(websocket: WebSocket):
    # --- Auth: token first, then origin, then accept. ---
    supplied = websocket.headers.get("x-agent-token", "")
    if not secrets.compare_digest(supplied, EXPECTED_TOKEN):
        await websocket.close(code=1008, reason="Invalid token")
        return

    # The only legitimate client is the Node `ws` library, which sends no
    # Origin header. Browsers always send one - so an Origin means a webpage
    # is trying to reach this localhost server. Reject before accepting.
    if websocket.headers.get("origin"):
        await websocket.close(code=1008, reason="Browser origins not permitted")
        return

    await websocket.accept()

    reader_task = None
    pending: dict[str, Future] = {}

    def release_pending():
        """Unblock any worker thread waiting on an approval that can no longer
        be answered (socket closed, panel disposed). Denying is the safe default."""
        for fut in pending.values():
            if not fut.done():
                fut.set_result(False)
        pending.clear()

    try:
        # --- Auth payload ---
        first_message = await websocket.receive_text()
        try:
            auth_data = json.loads(first_message)
            api_key = auth_data.get("api_key")
            # Default DENY: a malformed payload must lose the capability,
            # never gain it.
            allow_execution = bool(auth_data.get("allow_execution", False))
            if not api_key:
                raise ValueError("No API key found in payload")
        except (json.JSONDecodeError, ValueError):
            await websocket.close(code=1008, reason="Authentication failed")
            return

        # --- Working directory ---
        working_dir = await websocket.receive_text()

        loop = asyncio.get_running_loop()
        prompts: asyncio.Queue = asyncio.Queue()
        cancel_event=threading.Event()
        async def reader():
            """The ONLY coroutine that reads the socket after handshake."""
            try:
                while True:
                    raw = await websocket.receive_text()
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    kind = msg.get("type")
                    if kind == "approval":
                        fut = pending.pop(msg.get("id"), None)
                        if fut and not fut.done():
                            fut.set_result(bool(msg.get("approved")))
                    elif kind == "prompt":
                        await prompts.put(msg.get("text", ""))
                    elif kind =="cancel":
                        cancel_event.set()
            except (WebSocketDisconnect, RuntimeError):
                pass
            except asyncio.CancelledError:
                raise
            finally:
                release_pending()
                # Sentinel so the main loop exits instead of waiting forever.
                prompts.put_nowait(None)

        def request_approval(kind: str, path: str, content: str) -> bool:
            """Called FROM the agent's worker thread. Must not touch the loop
            directly - everything goes through run_coroutine_threadsafe."""
            approval_id = str(uuid.uuid4())
            fut: Future = Future()
            pending[approval_id] = fut

            try:
                asyncio.run_coroutine_threadsafe(
                    websocket.send_text("ASK:" + json.dumps({
                        "id": approval_id,
                        "kind": kind,
                        "path": path,
                        "content": content,
                    })),
                    loop,
                ).result(timeout=SEND_TIMEOUT)
            except Exception:
                pending.pop(approval_id, None)
                return False        # couldn't even ask -> deny

            try:
                return fut.result(timeout=APPROVAL_TIMEOUT)
            except Exception:
                pending.pop(approval_id, None)
                return False        # timeout -> deny

        def send_update(text: str):
            asyncio.run_coroutine_threadsafe(
                websocket.send_text(f"UPDATE:{text}"), loop
            )

        # Start reading before building the Agent, so nothing sent during
        # history/cache load is missed.
        reader_task = asyncio.create_task(reader())

        agent = Agent(working_dir, api_key=api_key, allow_execution=allow_execution)

        # --- Main loop: pull prompts off the queue, never off the socket. ---
        while True:
            user_message = await prompts.get()
            if user_message is None:        # reader signalled disconnect
                break
            cancel_event.clear()

            user_message = re.sub(
                r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', user_message
            ).strip()

            if not user_message:
                continue
            if len(user_message) > MAX_PROMPT_LENGTH:
                await websocket.send_text(
                    f"DONE:Message too long "
                    f"({len(user_message)}/{MAX_PROMPT_LENGTH} chars). Please shorten it."
                )
                continue

            try:
                reply = await loop.run_in_executor(
                    None, agent.chat,
                    user_message, False, send_update, request_approval,cancel_event
                )
                await websocket.send_text(f"DONE:{reply}")
                try:
                    await websocket.send_text("QUOTA:" + budget_report().replace("\n"," | "))
                except Exception:
                    pass
            except CancelledByUser:
                await websocket.send_text("DONE:Cancelled.")
            except Exception as e:
                print(f"Chat error: {e}")
                traceback.print_exc()
                await websocket.send_text(f"DONE:Error - {e}")

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Unexpected server error: {e}")
        traceback.print_exc()
        try:
            await websocket.send_text(f"DONE:Error - {e}")
        except Exception:
            pass
    finally:
        if reader_task is not None:
            reader_task.cancel()
        release_pending()


if __name__ == "__main__":
    # Port 0 = let the OS pick a free port. The extension parses the real port
    # from uvicorn's "Uvicorn running on ..." line.
    uvicorn.run(app, host="127.0.0.1", port=0)
