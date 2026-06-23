import os
import subprocess
def run_python_file(working_directory: str, file_path: str, args: list[str] | None = None) -> str:
    try:
        abs_working_dir= os.path.abspath(working_directory)
        #cleans up the path by removing ../ etc
        abs_file_path = os.path.normpath(os.path.join(abs_working_dir, file_path))
        #check if directory is within or oustide working directory        #look for longest common parent directory and if it matches working directory then its valid
        valid_target_dir = os.path.commonpath([abs_working_dir, abs_file_path]) == abs_working_dir
            
        if valid_target_dir==False:
            return f'Error: Cannot execute "{file_path}" as it is outside the permitted working directory'
        if not os.path.isfile(abs_file_path):
            return f'Error: "{file_path}" does not exist or is not a regular file'
        if abs_file_path.endswith(".py") == False:
            return f'Error: "{file_path}" is not a Python file'

        command = ["python", abs_file_path]
        if args is not None: 
            command.extend(args)
        obj=subprocess.run(command,cwd=abs_working_dir,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30)
        output_string=""
        if obj.returncode!=0:
            output_string+=f"Process exited with code {obj.returncode}"
        if obj.stdout=="" and obj.stderr=="":
            output_string+="No output produced"
        if obj.stdout:
            output_string+=f"STDOUT:{obj.stdout}"
        if obj.stderr:
            output_string+= f"STDERR:{obj.stderr}"
        return output_string
    except Exception as e:
        return f"Error: executing Python file: {e}"