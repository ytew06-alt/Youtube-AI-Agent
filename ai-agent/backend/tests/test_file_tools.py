import os
import tempfile
from functions.write_file import write_file
from functions.get_file_content import get_file_content
from functions.run_python_file import run_python_file


def test_write_creates_new_file():
    with tempfile.TemporaryDirectory() as ws:
        result = write_file(ws, "new.py", "print(1)")
        assert "Successfully" in result
        assert os.path.exists(os.path.join(ws, "new.py"))


def test_write_creates_parent_dirs():
    with tempfile.TemporaryDirectory() as ws:
        write_file(ws, "a/b/c.py", "x = 1")
        assert os.path.exists(os.path.join(ws, "a", "b", "c.py"))


def test_write_blocked_when_approval_denied():
    with tempfile.TemporaryDirectory() as ws:
        result = write_file(ws, "no.py", "x", request_approval=lambda *a: False)
        assert not os.path.exists(os.path.join(ws, "no.py"))
        assert "declined" in result.lower()


def test_write_proceeds_when_approved():
    with tempfile.TemporaryDirectory() as ws:
        write_file(ws, "yes.py", "x = 1", request_approval=lambda *a: True)
        assert os.path.exists(os.path.join(ws, "yes.py"))


def test_read_missing_file_message_is_clear():
    with tempfile.TemporaryDirectory() as ws:
        result = get_file_content(ws, "nope.py")
        assert "not found" in result.lower()


def test_run_rejects_non_python():
    with tempfile.TemporaryDirectory() as ws:
        open(os.path.join(ws, "a.txt"), "w").write("hi")
        assert "not a Python file" in run_python_file(ws, "a.txt")


def test_run_executes_and_captures_stdout():
    with tempfile.TemporaryDirectory() as ws:
        open(os.path.join(ws, "ok.py"), "w").write("print('hello')")
        assert "hello" in run_python_file(ws, "ok.py")