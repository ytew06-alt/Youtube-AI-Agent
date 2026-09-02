import os
from config import safe_resolve,is_sensitive
def write_file(working_directory: str, file_path: str, content: str,request_approval=None) -> str:
    try:
            #cleans up the path by removing ../ etc
            abs_file_path = safe_resolve(working_directory,file_path)
    except ValueError:
            return f'Error: Cannot read "{file_path}" as it is outside the permitted working directory'
    
            #check if directory is within or oustide working directory        #look for longest common parent directory and if it matches working directory then its valid
    if is_sensitive(file_path):
             return(f'Refused: "{file_path}" may contain secrets (API keys, tokens, '
                    f'private keys). Reading it is blocked. Ask the user to share '
                    f'only the specific value you need.')
    # if not os.path.isfile(abs_file_path):
    #     return f'Error: File not found or is not a regular file: "{file_path}"'
    
        #getting user validation for write file permission
    if request_approval is not None:
        if not request_approval("write",file_path,content):
            return (f'The user declined the write to "{file_path}". '
            f'The code has already been shown to them in the chat. '
            f'Do NOT attempt to write this file again and do NOT ask what '
            f'they would prefer. Acknowledge briefly and continue with the '
            f'rest of the task, or stop if nothing remains.')

    parent_dir=os.path.dirname(abs_file_path)
    os.makedirs(parent_dir,exist_ok=True)
    with open(abs_file_path,"w",encoding="utf-8") as f:
        f.write(content)
    
        return f'Successfully wrote to "{file_path}" ({len(content)} characters written)'

