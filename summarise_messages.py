from google.genai import types
from gemini_client import call_gemini_retry
from models import SUMMARY_MODEL
from gemini_client import call_with_fallback


def summarise_messages(client,messages):
    cumulative_text=""
    for message in messages:
        #the role of the message ie USER or MODEL etc
        if message.role is None:
            role="USER"
        else:
            role=message.role.upper()
        #text ofr current message being processed
        if message.parts is None:
            continue
        message_text=""
        for part in message.parts:
            #if part is a tool call, or not text, we skip it
            if part.text is not None:
                #adds space between the extracted text of each part of the message
                message_text+=part.text+" "
                #ensure we dont log blank messages
        if message_text.strip()!="":
            cumulative_text+=f"{role}: {message_text.strip()}\n"
    summary = (
    "Summarize this history in 2-3 sentences. Focus strictly on the technical state.\n"
    "Include:\n"
    "1. User's main goal\n"
    "2. Files/tools modified\n"
    "3. Current progress\n\n"
    "NO transcripts.\n\n"
    f"History:\n{cumulative_text}\n\n")

    response=call_with_fallback(client,model=SUMMARY_MODEL,contents=summary)
    if response.text is None:
        return "Summary unavailable for this segment."
    return response.text.strip()