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
from cache import Cache
import json
from summarise_messages import summarise_messages
import time
from google.genai import errors
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

def main():
    #load the API key from .env file
    load_dotenv()
    api_key=os.environ.get("GEMINI_API_KEY") 

    #create a client and generate a response from a user input prompt
    client=genai.Client(api_key=api_key)
    system_prompt = r"""You are an expert autonomous AI software engineer operating within a local development environment. 
Your primary goal is to fulfill the user's request accurately, safely, and with maximum efficiency.

### CORE DIRECTIVES
1. THINK BEFORE YOU ACT: Before calling any function, you must output a 'Thought:' explaining your reasoning and which tool you will use.
2. BE FRUGAL: Every tool call is expensive. Minimize the number of steps.
3. AVOID LOOPS: If a tool returns an error, do not retry the exact same action. Change your approach. 
4. DO NOT ASSUME: Never assume the contents of a file without reading it first via get_file_content.
5. STAY IN SCOPE: Only interact with files relevant to the user's immediate request.

### TOOL USAGE CONSTRAINTS
- get_files_info: Use this FIRST to understand the directory structure.
- get_file_content: Use this to read the source code.
- run_python_file: Use this to execute code. Always read the code before running it.
- write_file: Use this only when you have a complete solution.

If the user asks to modify a file:

1. Read it.
2. Produce complete replacement.
3. Write it.
4. Run tests if appropriate.

### WORKFLOW
For every interaction, follow this exact sequence:
1. Brief Plan: What do I need to do next?
2. Action: [Call the appropriate tool, or provide the final answer]
3. Observation: [Wait for the tool result]"""
    

    parser=argparse.ArgumentParser(description="Chatbot")
    #parser accepts one command line argument and stores it in the parser args
    parser.add_argument("user_prompt",type=str,help="User Prompt")
    #verbose argument added
    parser.add_argument("--verbose",action="store_true",help="Enable verbose output")

    #this reads what the user has typed
    args=parser.parse_args()
    #this contains the actual command line argument prompt typed by the user
    prompt=args.user_prompt
    #creates a list of messages for chat history
    #user role, parts is only one type text and is stored as a content obj
    messages=[]
    #load previous conversation history into messages list at the start
    if os.path.exists("history.json"):
        with open("history.json","r") as f:
            messages_list=json.load(f)
            for message in messages_list:
                messages.append(types.Content.model_validate(message))
    messages.append(types.Content(role="user",parts=[types.Part(text=args.user_prompt)]))
    max_iters=20
    cache=Cache()
    #load data from disk into cache so that cached items remain even if system is shut down
    cache.load_disk("cache.json")
    for x in range(max_iters):
        while True:
            try:
                response = client.models.generate_content(model="gemini-2.5-flash",contents=messages,config=types.GenerateContentConfig(tools=[available_functions],system_instruction=system_prompt))
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
        if args.verbose==True:
            print(f"User prompt: {args.user_prompt}")
            print(f"Prompt tokens: {response.usage_metadata.prompt_token_count}")
            print(f"Response tokens: {response.usage_metadata.candidates_token_count}")
        
        
        
        if response.candidates:
            for candidate in response.candidates:
                if candidate is None or candidate.content is None:
                    continue
                
                messages.append(candidate.content)
               
        if response.function_calls:
            for function_call in response.function_calls:
                
                result=call_function(function_call,args.verbose,cache)
                
                messages.append(result)
                cache.save_disk("cache.json")
        # if response.text is not None:
        #     print(response.text)
        #     cache.save_disk("cache.json")
        #     return
            
        else:
            #final message after iters
            # print(response.text)
            # print(response.function_calls)
            # print(response.candidates)
            # print(response.candidates[0].content.parts)
            
           
            if len(messages)>=10:
                # --- DEBUG 1: See the list before we chop it ---
                print_history_debug(messages, "BEFORE COMPRESSION")
                summary=summarise_messages(client,messages[:8])
                del messages[:8]
                # create the bridge (Model role) to prevent API errors due to alternating roles protocol
                ack_msg = types.Content(
                    role="model",
                    parts=[types.Part(text="Understood. I have logged the prior project state.")]
                )
                messages.insert(0,ack_msg)
                messages.insert(0,types.Content(role="user",parts=[types.Part(text=summary)]))
                print_history_debug(messages, "AFTER COMPRESSION")
            message_list=[]
            for message in messages:
                message_list.append(message.model_dump())
            with open("history.json","w") as f:
                json.dump(message_list,f,indent=4)
            print(response.text)
            return

main()