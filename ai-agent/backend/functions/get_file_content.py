import os
from config import MAX_CHARS
def get_file_content(working_directory: str, file_path: str) -> str:
    try:
        abs_working_dir= os.path.abspath(working_directory)
        #cleans up the path by removing ../ etc
        abs_file_path = os.path.normpath(os.path.join(abs_working_dir, file_path))
        #check if directory is within or oustide working directory        #look for longest common parent directory and if it matches working directory then its valid
        valid_target_dir = os.path.commonpath([abs_working_dir, abs_file_path]) == abs_working_dir
            
        if valid_target_dir==False:
            return f'Error: Cannot read "{file_path}" as it is outside the permitted working directory'
        if not os.path.isfile(abs_file_path):
            return f'Error: File not found or is not a regular file: "{file_path}"'

        with open(abs_file_path,"r") as f:
            file_content_string = f.read(MAX_CHARS)

            # After reading the first MAX_CHARS
            if f.read(1):
                file_content_string += f'[...File "{file_path}" truncated at {MAX_CHARS} characters]' 
            return file_content_string

    except:
        return "Error:"