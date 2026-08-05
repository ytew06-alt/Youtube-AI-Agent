import os
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
from gemini_client import call_gemini_retry
from models import AGENT_MODEL
from gemini_client import call_with_fallback
from config import workspace_key,state_path
from call_function import get_available_functions, call_function
from config import CancelledByUser


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
    def __init__(self,working_directory,api_key,allow_execution=False):
        self.ws_key=workspace_key(working_directory)

        self.working_directory=working_directory
        self.messages=[]
        self.max_iters=10
        self.on_update=None
        self.system_prompt=self.init_system_prompt()
        self.request_count=0
        self.cancel_event=None
        self.session_start=time.time()
        self.last_prompt_tokens=0
        self.request_approval=None
        self.allow_execution=allow_execution
        self.tools=get_available_functions(allow_execution)
        

        self.cache=Cache()
        self._load_history()
        self._load_cache()
        #load the API key from .env file
        

        #create a client and generate a response from a user input prompt
        self.client=genai.Client(api_key=api_key)

        
    def verify_thought_signature(self,content):
        if not content.parts:
            return content
        for part in content.parts:
            if part.function_call is not None:
                if part.thought_signature:
                    print(f"Signature is ok for {part.function_call.name} ({len(part.thought_signature)} bytes)")
                else:
                    print(f"WARNING: no signature for {part.function_call.name} — using fallback sentinel")
                    part.thought_signature = b"skip_thought_signature_validator"
                 # removed a break to allow for parallel tool calls
        return content
    def chat(self,prompt:str,verbose: bool,on_update=None,request_approval=None,cancel_event=None) ->str :
        self.request_approval=request_approval
        self.on_update=on_update
        self.cancel_event=cancel_event
        checkpoint=len(self.messages)
        if prompt.strip().lower() == "/clear":
            self.messages = [] # Empty the memory
            path=state_path("history.json",self.ws_key)
            if os.path.exists(path):
                os.remove(path) # Delete the saved file
            return "Conversation history cleared. Ready for a new task!"
        self.verbose=verbose
        self.messages.append(types.Content(role="user",parts=[types.Part(text=prompt)]))
        try:
            for i in range(self.max_iters):
                if self.cancel_event is not None and self.cancel_event.is_set():
                    raise CancelledByUser()
                
                response=self._call_model(on_update)
                try:
                    self._print_verbose(response)
                    usage=getattr(response,"usage_metadata",None)
                    if usage is not None:
                        self.last_prompt_tokens=usage.prompt_token_count or 0

                except Exception as e:
                    print(f"Usage accounting failed (ignoring): {e}")

                
                if response.usage_metadata:
                    self.last_prompt_tokens=response.usage_metadata.prompt_token_count or 0
                if response.candidates:
                    for candidate in response.candidates:
                        if candidate is None or candidate.content is None:
                            continue

                        self.messages.append(self.verify_thought_signature(candidate.content))
                    
                if response.function_calls:
                    #tells the extension whihc tools are called 
                    #allows to print each tool call like Calling get_file_content... in the http connection
                    for call in response.function_calls:
                        if on_update:
                            on_update(f"Calling tool: {call.name}...")
                    self._tool_calls(response.function_calls)
                    if self.cancel_event is not None and self.cancel_event.is_set():
                        raise CancelledByUser()
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
            del self.messages[checkpoint:]
            raise
        
            
        

    def _call_model(self,on_update=None):
            self.request_count += 1
            elapsed = time.time() - self.session_start
            print("\n" + "="*60)
            print(f"GEMINI REQUEST #{self.request_count}")
            print(f"Elapsed: {elapsed:.1f} seconds")
            print(f"Requests/min so far: {self.request_count / max(elapsed/60, 1/60):.2f}")
            print("="*60)
            return call_with_fallback(
                self.client,
                on_update=on_update, cancel_event=self.cancel_event,
                model=AGENT_MODEL,
                contents=self.messages,
                config=types.GenerateContentConfig(tools=[self.tools], system_instruction=self.system_prompt)
            )

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
                    result=call_function(function_call,self.working_directory,self.verbose,self.cache,client=self.client,allow_execution=self.allow_execution,request_approval=self.request_approval,on_update=self.on_update,cancel_event=self.cancel_event)
                    self.messages.append(result)
            self._save_cache()

    def safe_compression(self,min_cut=0):
        #never cuts mid turn so prevents cutting a function call from its function response
        for i in range(min_cut,len(self.messages)):
            msg=self.messages[i]
            if msg.role=="user" and msg.parts and any(part.text for part in msg.parts):
                return i
        return min_cut
    
    def _compress_history(self):
        if self.last_prompt_tokens<100000:
            return
            
        
        
        # --- DEBUG 1: See the list before we chop it ---
        print_history_debug(self.messages, "BEFORE COMPRESSION")

        cut=self.safe_compression(8)
        summary=summarise_messages(self.client,self.messages[:cut])
        del self.messages[:cut]
        # create the bridge (Model role) to prevent API errors due to alternating roles protocol
        ack_msg = types.Content(
            role="model",
            parts=[types.Part(text="Understood. I have logged the prior project state.")]
        )
        self.messages.insert(0,ack_msg)
        self.messages.insert(0,types.Content(role="user",parts=[types.Part(text=summary)]))
        print_history_debug(self.messages, "AFTER COMPRESSION")
    
    def _load_history(self):
        if os.path.exists(state_path("history.json", self.ws_key)):
            with open(state_path("history.json",self.ws_key),"r") as f:
                messages_list=json.load(f)
                for message in messages_list:
                    self.messages.append(types.Content.model_validate(message))
    
    def _save_history(self):
        message_list=[]
        for message in self.messages:
            message_list.append(message.model_dump(mode="json"))
        with open(state_path("history.json", self.ws_key), "w") as f:
            json.dump(message_list,f,indent=4)
    
    def _load_cache(self):
        self.cache.load_disk(state_path("cache.json", self.ws_key))


    def _save_cache(self):
        self.cache.save_disk(state_path("cache.json", self.ws_key))

    def _print_verbose(self, response):
        if not self.verbose:
            return
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            print("No usage metadata on this response")
            return
        print(f"Prompt tokens: {usage.prompt_token_count}")
        print(f"Response tokens: {usage.candidates_token_count}")
        
         
    def init_system_prompt(self)->str:
        return r"""
    You are an autonomous AI software engineer working in a local development environment.
    
Your objective is to solve the user's request accurately while minimising API usage, tool calls, and unnecessary reasoning loops.
Current session reminders:

    - Every model request counts towards a strict request budget.
    - Minimise the number of model turns.
    - Batch all independent tool calls.
    - Prefer one large batch of tool calls over many small batches.
    - Avoid re-reading information already obtained.
    
=========================
GENERAL BEHAVIOUR
=========================

- Think before acting.
- Form a complete plan before using any tools.
- Prefer solving problems with the information already available.
- Do not make assumptions about file contents.
- Never fabricate code or project structure.
- Keep responses concise unless the user requests detailed explanations.

=========================
TOOL USAGE
=========================

Tools are expensive. Use them deliberately.

Before calling any tool:

1. Decide ALL the information you will need.
2. Determine whether multiple tool calls can be executed independently.
3. Emit every independent tool call together in a single response.

Never request one file at a time if you already know you will need several.

Good:

get_file_content(main.py)
get_file_content(utils.py)
get_file_content(config.py)

Bad:

get_file_content(main.py)

(wait)

get_file_content(utils.py)

(wait)

get_file_content(config.py)

If multiple file reads are independent, request them together.

=========================
PROJECT INSPECTION
=========================

When working in an unfamiliar project:

- Prefer inspect_project first instead of repeatedly exploring directories.
- Use inspect_project once to understand the project.
- Afterwards only read the files that are actually relevant.

Do not repeatedly inspect the project unless the project structure may have changed.

=========================
READING FILES
=========================

Only read files that are relevant to the user's request.

Avoid reading:

- generated files
- unrelated modules
- large files that are clearly unnecessary

If several files are required to understand the problem, request all of them together.

=========================
WRITING FILES
=========================

Before writing:

- Read the target file if its current contents are unknown.
- Produce the complete updated file.
- Write the file once.

Avoid repeatedly rewriting the same file with small incremental edits.

=========================
RUNNING CODE
=========================

Only execute code when execution provides new information.

Do not repeatedly rerun the same failing command unless something has changed.

If execution fails:

- Analyse the error.
- Modify the code.
- Run again only if necessary.

=========================
ERROR RECOVERY
=========================

If a tool fails:

- Analyse why.
- Choose a different strategy.
- Do not repeat the exact same failing tool call.

=========================
MEMORY
=========================

Remember information returned by tools.

Never reread a file that has already been read unless:

- the file has been modified,
- the user requests it,
- or the previous information is insufficient.

=========================
EFFICIENCY
=========================

Your goal is to minimise model turns.

Always try to gather all required information before asking for another round of tool calls.

Prefer:

One planning step
→ Multiple independent tool calls
→ One reasoning step

instead of:

Reason
→ Tool
→ Reason
→ Tool
→ Reason
→ Tool

=========================
CODE QUALITY
=========================

Write clean, maintainable code.

Prefer simple solutions over clever ones.

Avoid introducing unnecessary abstractions.

Preserve the existing project style whenever practical.

=========================
FINAL RESPONSES
=========================

Before answering:

- Ensure the task is complete.
- Mention any limitations.
- Explain any assumptions you were forced to make."""
        
        
        
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