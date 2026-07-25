import os
from dotenv import load_dotenv
from google import genai
import argparse
#sys stores the command line arguments
import sys
from google.genai import types
from call_function import (available_functions,schema_get_files_info,schema_get_file_content,schema_write_file,schema_run_python_file,call_function)
from functions.get_files_info import get_files_info
from functions.get_file_content import get_file_content
from functions.run_python_file import run_python_file
from functions.write_file import write_file
from functions.inspect_project import inspect_project
from cache import Cache
import json
from summarise_messages import summarise_messages
import time
from google.genai import errors
from concurrent.futures import ThreadPoolExecutor

def print_history_debug(messages_list, stage_name="DEBUG"):
    """Helper to visualize the current state of the agent's memory."""
    print(f"\n=== {stage_name} (Length: {len(messages_list)}) ===")
    for i, msg in enumerate(messages_list):
        role = msg.role.upper() if msg.role else "USER/SYSTEM"
        
        # Extract text safely
        text = ""
        if msg.parts:
            for part in msg.parts:
                if part.text:
                    text += part.text + " "
                    
        # Truncate really long strings (like code blocks) for readability
        clean_text = text.strip()
        if len(clean_text) > 100:
            clean_text = clean_text[:97] + "..."
            
        print(f"[{i}] {role}: {clean_text}")
    print("=" * (10 + len(stage_name)) + "\n")

class Agent:
    def __init__(self,working_directory,api_key):
        self.working_directory=working_directory
        self.messages=[]
        self.max_iters=20
        self.system_prompt=self.init_system_prompt()

        self.cache=Cache()
        self._load_history()
        self._load_cache()
        #load the API key from .env file
        

        #create a client and generate a response from a user input prompt
        self.client=genai.Client(api_key=api_key)

        
    
    def chat(self,prompt:str,verbose: bool,on_update=None) ->str :
        self.verbose=verbose
        self.messages.append(types.Content(role="user",parts=[types.Part(text=prompt)]))
        try:
            for i in range(self.max_iters):
                
                response=self._call_model()
                self._print_verbose(response)
                if response.candidates:
                    for candidate in response.candidates:
                        if candidate is None or candidate.content is None:
                            continue
                        
                        self.messages.append(candidate.content)
                    
                if response.function_calls:
                    #tells the extension whihc tools are called 
                    #allows to print each tool call like Calling get_file_content... in the http connection
                    for call in response.function_calls:
                        if on_update:
                            on_update(f"Calling tool: {call.name}...")
                    self._tool_calls(response.function_calls)
                    continue
                else:
                    try:
                        self._compress_history()
                    except Exception as e:
                        print(f"History compression failed, skipping...: {e}")
                    self._save_history()
                    return response.text
            return "Max iterations reached"
        except Exception:
            del self.messages[len(self.messages):]
            raise

            


    def _call_model(self):
        while True:
            try:
                response = self.client.models.generate_content(model="gemini-2.5-flash",contents=self.messages,config=types.GenerateContentConfig(tools=[available_functions],system_instruction=self.system_prompt))
                break
            except errors.APIError as e:
                if e.code==429 or "RESOURCE_EXHAUSTED" in str(e):
                    print("Rate limit exceeded. Pausing for 60 seconds to cool down...")
                    time.sleep(60)
                else:
                    raise e

        if response is None:
            print("Invalid Response")
            raise RuntimeError

        return response

    def _tool_calls(self,function_calls):
        if function_calls:
            #multithreading tool calls for concurrency
            is_parallel=True
            for function_call in function_calls:
                if function_call.name!="get_file_content" and function_call.name !="get_files_info":
                    is_parallel=False
                    break
            if is_parallel:    
                with ThreadPoolExecutor() as executor:
                    #future stores the future object, if not generated yet it waits else it returns the result
                    futures=[]
                    for function_call in function_calls:
                        
                        futures.append(executor.submit(call_function,function_call,self.working_directory,self.verbose,self.cache))
                    for future in futures:
                        result=future.result()
                        print(f"USING MULTITHREADING!!!!")
                        self.messages.append(result)
            else:
                for function_call in function_calls:
                    result=call_function(function_call,self.working_directory,self.verbose,self.cache)
                    self.messages.append(result)
            self._save_cache()

    def _compress_history(self):
        if len(self.messages)<10:
            return
        
        # --- DEBUG 1: See the list before we chop it ---
        print_history_debug(self.messages, "BEFORE COMPRESSION")
        summary=summarise_messages(self.client,self.messages[:8])
        del self.messages[:8]
        # create the bridge (Model role) to prevent API errors due to alternating roles protocol
        ack_msg = types.Content(
            role="model",
            parts=[types.Part(text="Understood. I have logged the prior project state.")]
        )
        self.messages.insert(0,ack_msg)
        self.messages.insert(0,types.Content(role="user",parts=[types.Part(text=summary)]))
        print_history_debug(self.messages, "AFTER COMPRESSION")
    
    def _load_history(self):
        if os.path.exists("history.json"):
            with open("history.json","r") as f:
                messages_list=json.load(f)
                for message in messages_list:
                    self.messages.append(types.Content.model_validate(message))
    
    def _save_history(self):
        message_list=[]
        for message in self.messages:
            message_list.append(message.model_dump())
        with open("history.json","w") as f:
            json.dump(message_list,f,indent=4)
    
    def _load_cache(self):
        self.cache.load_disk("cache.json")


    def _save_cache(self):
        self.cache.save_disk("cache.json")

    def _print_verbose(self,response):
        if self.verbose==True:
            
            print(f"Prompt tokens: {response.usage_metadata.prompt_token_count}")
            print(f"Response tokens: {response.usage_metadata.candidates_token_count}")
        
         
    def init_system_prompt(self)->str:
        return r"""You are an autonomous AI software engineer working in a local development environment.

        Rules:
        - Minimize tool calls.
        - Never assume file contents; read files before modifying or executing them.
        - Only access files relevant to the user's request.
        - If a tool fails, do not repeat the same call without a different approach.
        - When modifying a file: read it, generate the complete replacement, write it, then test if appropriate.
        - If multiple tool calls are independent, emit them together in a single response. Only separate tool calls when one depends on another.
        Use inspect_project when you need an overview of an unfamiliar project or need to inspect multiple files.

        If the user asks about a specific file, use get_file_content instead.
        Before using tools, briefly explain your plan."""
        
        
        
def main():
    parser=argparse.ArgumentParser(description="Chatbot")
    #parser accepts one command line argument and stores it in the parser args
    parser.add_argument("user_prompt",type=str,help="User Prompt")
    #verbose argument added
    parser.add_argument("--verbose",action="store_true",help="Enable verbose output")

    #this reads what the user has typed
    args=parser.parse_args()

    agent_obj=Agent("./calculator")
    response=agent_obj.chat(args.user_prompt,args.verbose)
    print(response)

if __name__=="__main__": 
    main()