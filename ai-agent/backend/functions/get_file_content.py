import os
from config import MAX_CHARS,safe_resolve
def get_file_content(working_directory: str, file_path: str) -> str:
    try:
        #cleans up the path by removing ../ etc
        abs_file_path = safe_resolve(working_directory,file_path)
    except ValueError:
            return f'Error: Cannot read "{file_path}" as it is outside the permitted working directory'

        #check if directory is within or oustide working directory        #look for longest common parent directory and if it matches working directory then its valid
        
    if not os.path.isfile(abs_file_path):
        return f'Error: File not found or is not a regular file: "{file_path}"'


    with open(abs_file_path,"r") as f:
        file_content_string = f.read(MAX_CHARS)

        # After reading the first MAX_CHARS
        if f.read(1):
            file_content_string += f'[...File "{file_path}" truncated at {MAX_CHARS} characters]' 
        return file_content_string

    