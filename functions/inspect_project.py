import os
from functions.get_files_info import get_files_info
from functions.get_file_content import get_file_content
def inspect_project(working_directory,max_file_size=1000000):
    IGNORE = {
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "node_modules",
    }
    final_output=[]
    #imposing max char limits and max individual file size limits
    curr_chars=0
    max_chars=80000
     #1MB
    final_output.append(get_files_info(working_directory,"."))
    #going thru the working directory and subdirectories to get all files with .py and .md extensions
    for root,dirs,files in os.walk(working_directory):
        #ignore reading files in the ignore list
        dirs[:]=[d for d in dirs if d not in IGNORE]
        for file in files:
            if file.endswith((".py", ".md")):
                #create the full path of the file with the root
                file_path=os.path.join(root,file)
                if os.path.getsize(file_path) > max_file_size:
                    final_output.append(f"File: {file_path} exceeds the maximum file size of {max_file_size} bytes. Skipping content read.")
                    continue
                
                #get files content requires a relative path from the working dir
                relative_path=os.path.relpath(file_path,working_directory)
                content=get_file_content(working_directory,relative_path)
                if curr_chars + len(content)>max_chars:
                    return "\n".join(final_output)
                final_output.append(f"File: {relative_path}\nContent:\n{content}\n")
                curr_chars+=len(content)
        
    return "\n".join(final_output)

    
