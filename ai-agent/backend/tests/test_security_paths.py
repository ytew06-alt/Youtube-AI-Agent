import os
import tempfile
import pytest
from config import safe_resolve


def test_rejects_parent_traversal():
    with tempfile.TemporaryDirectory() as ws:
        for bad in ["../secret.txt", "../../etc/passwd", "a/../../out.txt",
                    "./../../out.txt", "sub/../../../out.txt"]:
            with pytest.raises(ValueError):
                safe_resolve(ws, bad)


def test_rejects_absolute_paths():
    with tempfile.TemporaryDirectory() as ws:
        for bad in ["/etc/passwd", "/tmp/evil.txt"]:
            with pytest.raises(ValueError):
                safe_resolve(ws, bad)


def test_rejects_null_byte():
    with tempfile.TemporaryDirectory() as ws:
        with pytest.raises(ValueError):
            safe_resolve(ws, "ok.txt\x00.png")


def test_allows_normal_paths():
    with tempfile.TemporaryDirectory() as ws:
        assert safe_resolve(ws, "main.py").startswith(os.path.realpath(ws))
        assert safe_resolve(ws, "src/app/main.py").startswith(os.path.realpath(ws))
        assert safe_resolve(ws, "./main.py").startswith(os.path.realpath(ws))


def test_rejects_symlink_escape():
    """A symlink INSIDE the workspace pointing outside must not be followed.
    This is the case os.path.abspath cannot catch - only realpath can."""
    with tempfile.TemporaryDirectory() as ws:
        outside = tempfile.NamedTemporaryFile(delete=False)
        outside.write(b"top secret")
        outside.close()
        link = os.path.join(ws, "escape")
        os.symlink(outside.name, link)
        try:
            with pytest.raises(ValueError):
                safe_resolve(ws, "escape")
        finally:
            os.unlink(outside.name)


def test_rejects_symlinked_directory_escape():
    with tempfile.TemporaryDirectory() as ws, tempfile.TemporaryDirectory() as other:
        with open(os.path.join(other, "secret.txt"), "w") as f:
            f.write("secret")
        os.symlink(other, os.path.join(ws, "linkdir"))
        with pytest.raises(ValueError):
            safe_resolve(ws, "linkdir/secret.txt")


def test_new_file_in_existing_dir_is_allowed():
    """Creating a file that does not exist yet must still resolve."""
    with tempfile.TemporaryDirectory() as ws:
        p = safe_resolve(ws, "brand_new.py")
        assert p.startswith(os.path.realpath(ws))