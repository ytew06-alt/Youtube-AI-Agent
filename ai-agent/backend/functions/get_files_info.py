import os
from google.genai import types

#essentially given a working directory and a requested directory we are checking if the requested path is within working dir
def get_files_info(working_directory: str, directory: str = ".") -> str:
    try:
        #abs dir gives full path compared to a relative path (working_directory) whihc is relative to the root directoru
        abs_working_dir= os.path.abspath(working_directory)
        #cleans up the path by removing ../ etc
        target_dir = os.path.normpath(os.path.join(abs_working_dir, directory))
        #check if directory is within or oustide working directory
        #look for longest common parent directory and if it matches working directory then its valid
        valid_target_dir = os.path.commonpath([abs_working_dir, target_dir]) == abs_working_dir
        
        if valid_target_dir==False:
            return f'Error: Cannot list "{directory}" as it is outside the permitted working directory'
        #is this path an actual directory
        if not os.path.isdir(target_dir):
            return f'Error: {directory} is not a directory'
        print(f'Success: "{directory}" is within the working directory')
        info_message=""
        contents=os.listdir(target_dir)
        for content in contents:
            content_path=os.path.join(target_dir,content)
            is_dir=os.path.isdir(content_path)
            size=os.path.getsize(content_path)
            info_message+=f"- {content}: file_size={size} bytes, is_dir={is_dir}\n"
        return info_message
    except:
        err_message=f"Error: {Exception}"
        return err_message

    