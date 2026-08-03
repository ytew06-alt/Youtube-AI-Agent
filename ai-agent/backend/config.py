import hashlib
import os
MAX_CHARS=10000

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