import hashlib
import os
MAX_CHARS=10000

SENSITIVE_NAMES = {
    "credentials.json", "credentials", ".npmrc", ".netrc",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", ".htpasswd",
}
SENSITIVE_SUFFIXES = (".pem", ".key", ".pfx", ".p12", ".keystore", ".jks")
SENSITIVE_DIRS = {".aws", ".ssh", ".gnupg"}


def is_sensitive(file_path: str) -> bool:
    """True for files that commonly hold secrets."""
    norm = os.path.normpath(file_path).replace("\\", "/")
    parts = norm.split("/")
    name = parts[-1].lower()

    if name.startswith(".env"):
        return True
    if name in SENSITIVE_NAMES:
        return True
    if name.endswith(SENSITIVE_SUFFIXES):
        return True
    if any(p.lower() in SENSITIVE_DIRS for p in parts[:-1]):
        return True
    return False


STATE_DIR = os.environ.get("AI_AGENT_STATE_DIR", ".")
os.makedirs(STATE_DIR, exist_ok=True)
#prevents symlinks that are malicious so agent stays inside working dir
def safe_resolve(working_directory:str,file_path:str)->str:
    if "\x00" in file_path:
        raise ValueError("path contains a null byte")
    abs_working_dir=os.path.realpath(working_directory)
    candidate=os.path.realpath(os.path.join(abs_working_dir,file_path))
    try:
        common=os.path.commonpath([abs_working_dir,candidate])
    except ValueError:
        raise ValueError("path is outside the permitted working directory")

    if common!= abs_working_dir:
        raise ValueError("path is outside permitted working directory")

    return candidate
    


def state_path(name,ws_key=None):
    if ws_key:
        stem, ext=os.path.splitext(name)
        name=f"{stem}-{ws_key}{ext}"
    return os.path.join(STATE_DIR,name)


def workspace_key(working_dir):
    #normalised to deal with capitals, and abs path so project and home/bilal/project for eg is the hashed the same
    normalised_path=os.path.normcase(os.path.abspath(working_dir))
    return hashlib.sha256(normalised_path.encode()).hexdigest()[:16]


class CancelledByUser(Exception):
    """Raised when a user cancel a running process, clean stop not an error"""
    pass
