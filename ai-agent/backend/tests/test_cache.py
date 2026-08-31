import time
from cache import Cache
from call_function import generate_key


def test_generate_key_does_not_mutate_input():
    args = {"file_path": "./src/../main.py"}
    original = dict(args)
    generate_key("get_file_content", args)
    assert args == original


def test_key_includes_file_path_prefix():
    key = generate_key("get_file_content", {"file_path": "main.py"})
    assert key.startswith("file_path:main.py|")


def test_invalidation_actually_removes_entries():
    c = Cache()
    key = generate_key("get_file_content", {"file_path": "main.py"})
    c.set(key, "old contents", 3600)
    assert c.get(key) == "old contents"
    c.invalid_multiple_keys("main.py")
    assert c.get(key) is None


def test_invalidation_does_not_hit_similar_names():
    c = Cache()
    k1 = generate_key("get_file_content", {"file_path": "main.py"})
    k2 = generate_key("get_file_content", {"file_path": "main.py.bak"})
    c.set(k1, "a", 3600)
    c.set(k2, "b", 3600)
    c.invalid_multiple_keys("main.py")
    assert c.get(k1) is None
    assert c.get(k2) == "b"


def test_expiry():
    c = Cache()
    c.set("k", "v", 1)
    assert c.get("k") == "v"
    time.sleep(1.1)
    assert c.get("k") is None


def test_corrupt_file_does_not_crash(tmp_path):
    p = tmp_path / "cache.json"
    p.write_text("{ this is not json")
    c = Cache()
    c.load_disk(str(p))
    assert c.size() == 0