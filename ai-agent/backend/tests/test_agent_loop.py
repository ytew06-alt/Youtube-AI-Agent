import os
import tempfile
import types
import agent_class
from agent_class import Agent
from config import CancelledByUser
import pytest


def make_part(text=None, function_call=None):
    p = types.SimpleNamespace(text=text, function_call=function_call,
                              thought_signature=b"sig")
    return p


def make_response(text=None, calls=None):
    parts = []
    if text:
        parts.append(make_part(text=text))
    for c in (calls or []):
        parts.append(make_part(function_call=c))
    content = types.SimpleNamespace(parts=parts, role="model")
    candidate = types.SimpleNamespace(content=content)
    return types.SimpleNamespace(
        candidates=[candidate],
        function_calls=list(calls or []),
        text=text,
        usage_metadata=types.SimpleNamespace(
            prompt_token_count=100, candidates_token_count=50),
    )


class FakeCall:
    def __init__(self, name, args):
        self.name = name
        self.args = args


@pytest.fixture
def agent(monkeypatch):
    ws = tempfile.mkdtemp()
    monkeypatch.setattr(agent_class.genai, "Client", lambda api_key: object())
    a = Agent(ws, api_key="fake", allow_execution=False)
    a.messages = []
    return a


def script(monkeypatch, responses):
    """Feed the agent a fixed sequence of model responses."""
    seq = iter(responses)
    monkeypatch.setattr(agent_class, "call_with_fallback",
                        lambda *a, **k: next(seq))


def test_simple_text_reply(agent, monkeypatch):
    script(monkeypatch, [make_response(text="All done.")])
    assert agent.chat("hi", False) == "All done."


def test_tool_then_reply(agent, monkeypatch):
    call = FakeCall("get_files_info", {"directory": "."})
    script(monkeypatch, [make_response(calls=[call]),
                         make_response(text="Found them.")])
    assert agent.chat("list files", False) == "Found them."
    assert any(m.role == "tool" for m in agent.messages)


def test_execution_blocked_when_not_allowed(agent, monkeypatch):
    call = FakeCall("run_python_file", {"file_path": "x.py"})
    script(monkeypatch, [make_response(calls=[call]),
                         make_response(text="Cannot run.")])
    agent.chat("run it", False)
    tool_msgs = [m for m in agent.messages if m.role == "tool"]
    assert any("disabled" in str(m.parts[0].function_response.response).lower()
               for m in tool_msgs)


def test_rejected_write_does_not_create_file(agent, monkeypatch):
    call = FakeCall("write_file", {"file_path": "x.py", "content": "print(1)"})
    script(monkeypatch, [make_response(calls=[call]),
                         make_response(text="Understood.")])
    agent.chat("write it", False, request_approval=lambda *a: False)
    assert not os.path.exists(os.path.join(agent.working_directory, "x.py"))


def test_max_iters_terminates(agent, monkeypatch):
    call = FakeCall("get_files_info", {"directory": "."})
    script(monkeypatch, [make_response(calls=[call]) for _ in range(20)])
    assert agent.chat("loop", False) == "Max iterations reached"


def test_cancel_rolls_back_messages(agent, monkeypatch):
    import threading
    ev = threading.Event()
    ev.set()
    script(monkeypatch, [make_response(text="never reached")])
    before = len(agent.messages)
    with pytest.raises(CancelledByUser):
        agent.chat("go", False, cancel_event=ev)
    assert len(agent.messages) == before


def test_history_round_trip(agent, monkeypatch):
    script(monkeypatch, [make_response(text="saved")])
    agent.chat("hi", False)
    agent._save_history()
    fresh = Agent(agent.working_directory, api_key="fake")
    assert len(fresh.messages) == len(agent.messages)