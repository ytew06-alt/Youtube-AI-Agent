"""
Gemini API wrapper: client-side rate limiting, quota-aware retries, model fallback.

Mechanism only - all model IDs and limits live in models.py.

Three failure modes, three different correct responses:
  429 + PerMinute quota  -> wait a bit, retry same model
  429 + PerDay quota     -> retrying today is pointless, fall back to another model
  503 UNAVAILABLE        -> Google's capacity problem, not yours; fall back
"""

import json
import random
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from config import state_path

from google.genai import errors
from config import CancelledByUser

from models import (
    DEFAULT_LIMITS,
    FALLBACK_CHAIN,
    MODEL_LIMITS,
    RPD_SAFETY_MARGIN,
)

USAGE_FILE = "gemini_usage.json"
PACIFIC = timezone(timedelta(hours=-8))  # PST; PDT is -7, the margin absorbs it


class QuotaExhausted(RuntimeError):
    """Daily quota for this model is gone. Retrying it today will not help."""

    def __init__(self, model, message, resets_at=None):
        self.model = model
        self.resets_at = resets_at
        super().__init__(message)


def _pacific_day():
    return datetime.now(PACIFIC).strftime("%Y-%m-%d")


def _next_pacific_midnight_local():
    now_pt = datetime.now(PACIFIC)
    midnight_pt = (now_pt + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return midnight_pt.astimezone()


class RateLimiter:
    """Spaces requests to stay inside RPM, and tracks RPD across restarts."""

    def __init__(self, usage_file=USAGE_FILE):
        self.usage_file = usage_file or state_path(USAGE_FILE)
        self._lock = threading.Lock()
        self._recent = {}   # model -> deque of monotonic timestamps
        self._daily = self._load()

    def _load(self):
        try:
            with open(self.usage_file) as f:
                data = json.load(f)
            if data.get("day") == _pacific_day():
                return data
        except (OSError, ValueError):
            pass
        return {"day": _pacific_day(), "counts": {}}

    def _save(self):
        try:
            with open(self.usage_file, "w") as f:
                json.dump(self._daily, f)
        except OSError:
            pass

    def _roll_day(self):
        today = _pacific_day()
        if self._daily.get("day") != today:
            self._daily = {"day": today, "counts": {}}
            self._save()

    def remaining_today(self, model):
        with self._lock:
            self._roll_day()
            limits = MODEL_LIMITS.get(model, DEFAULT_LIMITS)
            used = self._daily["counts"].get(model, 0)
            return max(0, limits["rpd"] - RPD_SAFETY_MARGIN - used)

    def acquire(self, model, on_update=None,cancel_event=None):
        """Block until it is safe to send. Raises QuotaExhausted if RPD is spent."""
        limits = MODEL_LIMITS.get(model, DEFAULT_LIMITS)
        min_interval = 60.0 / limits["rpm"]

        while True:
            with self._lock:
                self._roll_day()
                used = self._daily["counts"].get(model, 0)
                budget = limits["rpd"] - RPD_SAFETY_MARGIN
                if used >= budget:
                    reset = _next_pacific_midnight_local()
                    raise QuotaExhausted(
                        model,
                        f"Local daily budget for {model} spent ({used}/{budget}). "
                        f"Resets around {reset:%Y-%m-%d %H:%M %Z}.",
                        resets_at=reset,
                    )

                window = self._recent.setdefault(model, deque())
                now = time.monotonic()
                while window and now - window[0] >= 60.0:
                    window.popleft()

                wait = 0.0
                if window:
                    wait = max(wait, min_interval - (now - window[-1]))
                if len(window) >= limits["rpm"]:
                    wait = max(wait, 60.0 - (now - window[0]) + 0.5)

                if wait <= 0:
                    window.append(now)
                    self._daily["counts"][model] = used + 1
                    self._save()
                    return

            # NOT an error - normal pacing. Worded so it doesn't look like a
            # rate-limit failure in the chat UI.
            msg = (
                f"Spacing next call to {model}: {wait:.0f}s "
                f"(staying under {limits['rpm']}/min - not an error)"
            )
            print(msg)
            if on_update:
                on_update(msg)
            time.sleep(wait)
            _sleep_or_cancel(wait,cancel_event)

    def refund(self, model):
        """Undo a reservation when the request was rejected without doing work.

        Must undo BOTH dimensions. Only decrementing the daily count leaves a
        stale timestamp in the rolling window, which then makes the retry wait
        out a full min_interval for no reason.
        """
        with self._lock:
            window = self._recent.get(model)
            if window:
                window.pop()
            used = self._daily["counts"].get(model, 0)
            if used > 0:
                self._daily["counts"][model] = used - 1
                self._save()


_limiter = RateLimiter()


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------
def _error_details(e):
    raw = getattr(e, "details", None)
    if isinstance(raw, dict):
        return raw.get("error", raw)
    return {}


def classify(e):
    """Return (kind, retry_after_seconds).

    kind is one of: 'per_day', 'per_minute', 'unavailable', 'fatal'.
    """
    code = getattr(e, "code", None)
    err = _error_details(e)
    retry_after = None
    kind = None

    for d in err.get("details", []) or []:
        dtype = d.get("@type", "")
        if dtype.endswith("RetryInfo"):
            delay = str(d.get("retryDelay", "")).rstrip("s")
            try:
                retry_after = int(float(delay)) + 2
            except ValueError:
                pass
        elif dtype.endswith("QuotaFailure"):
            for v in d.get("violations", []) or []:
                qid = str(v.get("quotaId", "")) + str(v.get("quotaMetric", ""))
                if "PerDay" in qid or "per_day" in qid:
                    kind = "per_day"
                elif kind is None:
                    kind = "per_minute"

    if kind:
        return kind, retry_after

    text = str(e)
    if code == 429 or "RESOURCE_EXHAUSTED" in text:
        if "per day" in text.lower() or "PerDay" in text:
            return "per_day", retry_after
        return "per_minute", retry_after
    if code in (500, 503) or "UNAVAILABLE" in text or "overloaded" in text.lower():
        return "unavailable", retry_after
    return "fatal", retry_after


# ---------------------------------------------------------------------------
# Single-model call with retries
# ---------------------------------------------------------------------------
def call_gemini_retry(client, max_retries=3, on_update=None,cancel_event=None,**kwargs):
    """generate_content against ONE model, with pacing and backoff.

    Prefer call_with_fallback() in application code.
    """
    model = kwargs.get("model") or "unknown"

    for attempt in range(max_retries):
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledByUser()
        _limiter.acquire(model, on_update=on_update)
        try:
            return client.models.generate_content(**kwargs)
        except errors.APIError as e:
            kind, retry_after = classify(e)
            print(f"[gemini] {kind} on {model} (code={getattr(e, 'code', '?')}): {e}")

            # Rejected requests don't consume server-side quota - hand the slot back.
            if kind in ("per_minute", "unavailable"):
                _limiter.refund(model)

            if kind == "per_day":
                reset = _next_pacific_midnight_local()
                raise QuotaExhausted(
                    model,
                    f"Daily quota for {model} exhausted server-side. "
                    f"Resets around {reset:%Y-%m-%d %H:%M %Z}.",
                    resets_at=reset,
                ) from e

            if kind == "fatal" or attempt == max_retries - 1:
                raise

            wait = retry_after if retry_after else min(60, (2 ** attempt) * 5)
            wait += random.uniform(0, 2)  # jitter
            msg = (
                f"{kind} on {model} (attempt {attempt + 1}/{max_retries}); "
                f"retrying in {wait:.0f}s"
            )
            print(msg)
            if on_update:
                on_update(msg)
            _sleep_or_cancel(wait,cancel_event)

    raise RuntimeError("Max retries exceeded")


# ---------------------------------------------------------------------------
# Model fallback - this is what application code should call
# ---------------------------------------------------------------------------
def strip_thought_signatures(contents):
    """Remove thought signatures from history.

    Signatures are model-specific. Replaying Flash's signatures at Flash-Lite
    can be rejected, so clear them before a cross-model fallback.
    """
    if not isinstance(contents, list):
        return contents
    for msg in contents:
        for part in getattr(msg, "parts", None) or []:
            if getattr(part, "thought_signature", None):
                part.thought_signature = None
    return contents


def call_with_fallback(client, on_update=None, cancel_event=None, **kwargs):
    """Try the requested model, degrading through FALLBACK_CHAIN on 503/quota.

    Does NOT fall back on 'fatal' errors (400 bad request, 404 unknown model,
    auth failures) - those fail identically on every model and would just burn
    quota on the fallback too.
    """
    primary = kwargs.get("model")
    candidates = [primary] + list(FALLBACK_CHAIN.get(primary, []))
    last_err = None

    for i, model in enumerate(candidates):
        kwargs["model"] = model

        if i > 0:
            msg = f"{primary} unavailable - falling back to {model}"
            print(msg)
            if on_update:
                on_update(msg)
            kwargs["contents"] = strip_thought_signatures(kwargs.get("contents"))

        try:
            return call_gemini_retry(client, on_update=on_update,cancel_event=cancel_event, **kwargs)

        except QuotaExhausted as e:
            last_err = e
            continue

        except errors.APIError as e:
            kind, _ = classify(e)
            if kind in ("unavailable", "per_minute", "per_day"):
                last_err = e
                continue
            raise  # fatal - fallback won't help

    kwargs["model"] = primary  # don't leave the caller's dict mutated
    raise last_err

def _sleep_or_cancel(seconds,cancel_event):
    #constantly checks for a cancel event every second
    end=time.time() + seconds
    while True:
        remaining = end - time.time()
        if remaining<=0:
            return

        if cancel_event is not None and cancel_event.is_set():
            raise CancelledByUser()
        time.sleep(min(1,remaining))


def budget_report():
    lines = [f"Pacific day: {_pacific_day()}"]
    for m, limits in MODEL_LIMITS.items():
        used = _limiter._daily["counts"].get(m, 0)
        lines.append(
            f"  {m}: {used}/{limits['rpd']} used today, "
            f"{_limiter.remaining_today(m)} left, {limits['rpm']} RPM"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print(budget_report())
    print("Next Pacific reset (local):", _next_pacific_midnight_local())
