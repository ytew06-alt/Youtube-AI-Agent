import os
def write_file(working_directory: str, file_path: str, content: str) -> str:
    try:
        abs_working_dir= os.path.abspath(working_directory)
        #cleans up the path by removing ../ etc
        abs_file_path = os.path.normpath(os.path.join(abs_working_dir, file_path))
        #check if directory is within or oustide working directory        #look for longest common parent directory and if it matches working directory then its valid
        valid_target_dir = os.path.commonpath([abs_working_dir, abs_file_path]) == abs_working_dir
                
        if valid_target_dir==False:
            return f'Error: Cannot write to "{file_path}" as it is outside the permitted working directory'
        if os.path.isdir(abs_file_path):
            return f'Error: Cannot write to "{file_path}" as it is a directory'
        #essentially the file itself is not part of the directory its aa file name
        #so we make directory from the parent path since they are not files but folders/directories
        parent_dir=os.path.dirname(abs_file_path)
        os.makedirs(parent_dir,exist_ok=True)
        with open(abs_file_path,"w") as f:
            f.write(content)
        
            return f'Successfully wrote to "{file_path}" ({len(content)} characters written)'
    except:
        return f"Error:"
