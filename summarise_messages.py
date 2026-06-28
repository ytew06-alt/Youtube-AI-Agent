from google.genai import types

def summarise_messages(client,messages):
    cumulative_text=""
    for message in messages:
        #the role of the message ie USER or MODEL etc
        if message.role is None:
            role="USER"
        else:
            role=message.role.upper()
        #text ofr current message being processed
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

    response=client.models.generate_content(model="gemini-2.5-flash",contents=summary)

    return response.text.strip()