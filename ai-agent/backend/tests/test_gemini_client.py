import time
import pytest
from gemini_client import classify, _sleep_or_cancel
from config import CancelledByUser


class FakeAPIError(Exception):
    def __init__(self, code, details, message=""):
        super().__init__(message or str(details))
        self.code = code
        self.details = details


def test_classifies_per_day():
    err = FakeAPIError(429, {"error": {"details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
         "violations": [{"quotaId": "GenerateRequestsPerDayPerProject"}]}
    ]}})
    kind, _ = classify(err)
    assert kind == "per_day"


def test_classifies_per_minute():
    err = FakeAPIError(429, {"error": {"details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
         "violations": [{"quotaId": "GenerateRequestsPerMinutePerProject"}]}
    ]}})
    kind, _ = classify(err)
    assert kind == "per_minute"


def test_classifies_503_unavailable():
    err = FakeAPIError(503, {"error": {"code": 503, "status": "UNAVAILABLE"}})
    kind, _ = classify(err)
    assert kind == "unavailable"


def test_classifies_400_as_fatal():
    err = FakeAPIError(400, {"error": {"code": 400, "status": "INVALID_ARGUMENT"}})
    kind, _ = classify(err)
    assert kind == "fatal"


def test_sleep_never_goes_negative():
    """Regression: the 'sleep length must be non-negative' crash."""
    start = time.time()
    _sleep_or_cancel(0.05, None)
    assert time.time() - start >= 0.0


def test_sleep_cancels_early():
    import threading
    ev = threading.Event()
    ev.set()
    with pytest.raises(CancelledByUser):
        _sleep_or_cancel(30, ev)