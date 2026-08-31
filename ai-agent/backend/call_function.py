from google.genai import types
import os
from collections.abc import Callable
from functions.get_files_info import get_files_info
from functions.get_file_content import get_file_content
from functions.write_file import write_file
from functions.run_python_file import run_python_file
from functions.inspect_project import inspect_project
from functions.extract_from_youtube import extract_code_from_video
from cache import Cache
import json
from config import CancelledByUser
 
def generate_key(function_name: str, args:dict) ->str:
    #generate a hashing key based on function name and args to store in the cache itself
    #convert the dcitionary of args into a JSON string like {"directory: "calculator"} etc
    #sort keys so order is consistent and we get the same key for the same args regardless of order

    #if the file path key exists, then the value there whihc is a file path is converted into the normalized path (ie file name like lorem.txt and not the whole dreictory)
    #the prefix creates a unique tag for this for ease invalidation later when we write to a file and want to invalidate all cache entries related to that file path
    #if no file path in args then no prefix is added and we jsut generate the key based on function name and args as normal
    if "file_path" in args:
        normalised_path=os.path.normpath(args["file_path"])
        args={**args,"file_path": normalised_path}
        prefix=f"file_path:{args['file_path']}"
    else:
        prefix=""
    json_args=json.dumps(args,sort_keys=True)
    return f"{prefix}|{function_name}:{json_args}"


schema_get_files_info = types.FunctionDeclaration(
        name="get_files_info",
        description="Lists files in a specified directory relative to the working directory, providing file size and directory status",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "directory": types.Schema(
                    type=types.Type.STRING,
                    description="Directory path to list files from, relative to the working directory (default is the working directory itself)",
                ),
            },
        ),
        )


schema_get_file_content = types.FunctionDeclaration(
    name="get_file_content",
    description="Reads the contents of a file relative to the working directory.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="Path to the file to read, relative to the working directory.",
            ),
        },
    ),
)

schema_write_file = types.FunctionDeclaration(
    name="write_file",
    description="Writes text to a file relative to the working directory, creating parent directories if necessary.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="Path to the file to write, relative to the working directory.",
            ),
            
            "content": types.Schema(
                type=types.Type.STRING,
                description="The text content to write to the file.",
            ),
        },
        required=["file_path","content"],
    ),
)

schema_run_python_file = types.FunctionDeclaration(
    name="run_python_file",
    description="Runs a Python file relative to the working directory with optional command-line arguments.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="Path to the Python file to execute, relative to the working directory.",
            ),
            "args": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(
                    type=types.Type.STRING,
                ),
                description="Optional command-line arguments passed to the Python script.",
            ),
        },
    ),
)

schema_inspect_project=types.FunctionDeclaration(
    name="inspect_project",
    description="Provides the details of the project by returning directory,structure and contents of small .py and .md files",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "max_file_size": types.Schema(
                type=types.Type.INTEGER,
                description="max file size in bytes to include"
            )
        }
    )
    
)

schema_extract_from_youtube = types.FunctionDeclaration(
    name="extract_from_youtube",
    description="Extracts and reconstructs code from a coding tutorial Youtube video by watching it directly.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "url" : types.Schema(type=types.Type.STRING, description="Public YouTube URL of the coding tutorial")

        },
        required=["url"]
    )
)


def get_available_functions(allow_execution: bool = False) -> types.Tool:
    declarations = [
        schema_get_files_info,
        schema_get_file_content,
        schema_write_file,
        schema_inspect_project,
        schema_extract_from_youtube,
    ]
    if allow_execution:
        declarations.append(schema_run_python_file)
    return types.Tool(function_declarations=declarations)


available_functions = get_available_functions(allow_execution=True)


#the types.functionCall object has a name and args property
def call_function(function_call: types.FunctionCall,working_directory, verbose: bool = False,cache:Cache=None, ttl: int=3600,client=None,allow_execution=False,request_approval=None,on_update=None,cancel_event=None) -> types.Content:
    #if function call is get_file_content or get_files_info, check if the result is already cached
    #generate a key based on the name and args and see if it exists alr in the cache 
    #if exsits return the cached result instead of calling the function again and print that we are using the cached result if verbose is true
    if cache is not None:
        cache.clean_expired()
    if function_call.name == "get_file_content" or function_call.name == "get_files_info" or function_call.name=="inspect_project":
        key=generate_key(function_call.name,function_call.args)
        if cache is not None:
            cached=cache.get(key)
            if cached is not None:
                if verbose:
                    print(f" - Using cached result for function: {function_call.name}({function_call.args})")
                return types.Content(
                    role="tool",
                    parts=[
                        types.Part.from_function_response(
                            name=function_call.name,
                            response={"result": cached},
                        )])

    

    if verbose:
        print(f"Calling function: {function_call.name}({function_call.args})")
    else:
        print(f" - Calling function: {function_call.name}")
    
    #mapping to map names to the actual functions in a dict

    function_map: dict[str, Callable[..., str]] = {
    "get_file_content": get_file_content,
    "write_file":write_file,
    "run_python_file":run_python_file,
    "get_files_info":get_files_info,
    "inspect_project": inspect_project,
    "extract_from_youtube": extract_code_from_video
    }
    if function_call.name == "run_python_file" and not allow_execution:
        return types.Content(
            role="tool",
            parts=[
                types.Part.from_function_response(
                    name=function_call.name,
                    response={"error": "Code execution is disabled. The user has not "
                                       "granted permission to run files in this workspace."},
                )
            ],
        )

    if verbose:
        print(f"Calling function: {function_call.name}({function_call.args})")
    func = function_map.get(function_call.name)

    if func is None:
        return types.Content(
        role="tool",
        parts=[
            types.Part.from_function_response(
                name=function_call.name,
                response={"error": f"Unknown function: {function_call.name}"},
            )
        ],
        )
    args = dict(function_call.args) if function_call.args else {}
    if function_call.name== "extract_from_youtube":
        result=func(client=client,**args,on_update=on_update,cancel_event=cancel_event) if client else func(**args)
    elif function_call.name=="write_file":
        result=func(working_directory,request_approval=request_approval,**args)
    else:
        
        #** passes a dictionary and calculator is the workinf dir
        result=func(working_directory,**args)

    if cache is not None and (function_call.name=="get_file_content" or function_call.name=="get_files_info" or function_call.name=="inspect_project"):
        key=generate_key(function_call.name,function_call.args)
        if not result.startswith("Error:"):
            cache.set(key,result,ttl)
        #if u read a file and store content and write that file anf then read it again so we wud get stale data from cache
    if cache is not None and function_call.name=="write_file":
        cache.invalid_multiple_keys(args["file_path"])
        cache.invalidate_prefix("inspect_project:")
        cache.invalidate_prefix("get_files_info:")
    #packages string result from functions output into a types.content obj
    return types.Content(
    role="tool",
    parts=[
        types.Part.from_function_response(
            name=function_call.name,
            response={"result": result},
        )
    ],
    )

#-> is a hint to its return type for documentation and IDEs
#types.content fits gives gemini all the information in an obj rather than a string

