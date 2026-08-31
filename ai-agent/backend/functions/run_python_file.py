import os
import subprocess
import sys
from config import safe_resolve


def run_python_file(working_directory: str, file_path: str, args: list[str] | None = None) -> str:
    try:
        python_exe = sys.executable
        if python_exe is None:
            return "Error: No Python interpreter found on this system"

        abs_working_dir = os.path.realpath(working_directory)

        try:
            # cleans up the path by removing ../ etc, symlinks included
            abs_file_path = safe_resolve(working_directory, file_path)
        except ValueError:
            return f'Error: Cannot read "{file_path}" as it is outside the permitted working directory'

        if not os.path.isfile(abs_file_path):
            return f'Error: File not found or is not a regular file: "{file_path}"'
        if abs_file_path.endswith(".py") == False:
            return f'Error: "{file_path}" is not a Python file'

        command = [python_exe, abs_file_path]
        if args is not None:
            command.extend(args)
        obj = subprocess.run(command, cwd=abs_working_dir, stdout=subprocess.PIPE,stdin=subprocess.DEVNULL,
                             stderr=subprocess.PIPE, text=True, timeout=30)
        output_string = ""
        if obj.returncode != 0:
            output_string += f"Process exited with code {obj.returncode}"
        if obj.stdout == "" and obj.stderr == "":
            output_string += "No output produced"
        if obj.stdout:
            output_string += f"STDOUT:{obj.stdout}"
        if obj.stderr:
            output_string += f"STDERR:{obj.stderr}"
        return output_string
    except Exception as e:
        return f"Error: executing Python file: {e}"