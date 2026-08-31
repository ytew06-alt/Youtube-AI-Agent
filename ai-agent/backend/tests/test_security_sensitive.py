import pytest
from config import is_sensitive


@pytest.mark.parametrize("path", [
    ".env", ".env.local", ".env.production", ".ENV",
    "config/.env", "id_rsa", "server.pem", "cert.key",
    "credentials.json", ".npmrc", ".aws/credentials",
    ".ssh/id_ed25519", "keystore.jks",
])
def test_blocks_secrets(path):
    assert is_sensitive(path) is True


@pytest.mark.parametrize("path", [
    "environment.py", "keyboard.js", "main.py", "README.md",
    "env_utils.py", "src/keys.py", "monkey.txt", "package.json",
])
def test_allows_normal_files(path):
    assert is_sensitive(path) is False