from fastapi import FastAPI, WebSocket,WebSocketDisconnect
from agent_class import Agent
import uvicorn
import asyncio
#The main thing this does is that norammly u wud write terminal command
#That terminal command wud run python load history load cache load agemt and everything
#using fastapi and websockets the connection opens and these things remain open for infinite requests
#till the server is closed

#python server.py
#      ↓
# FastAPI app object is created
#       ↓
# uvicorn starts listening on localhost:8000
#       ↓
# startup() fires → prints your message
#       ↓
# Server sits idle waiting for WebSocket connections...
#       ↓
# VS Code extension connects to ws://localhost:8000/chat
#       ↓
# chat_endpoint() starts running for that connection

app=FastAPI()

#websocket endpoint
@app.websocket("/chat")
async def chat_endpoint(websocket: WebSocket):
    #handshake to open the connection
    await websocket.accept()
    #get the working directory input from the extension
    working_dir= await websocket.receive_text()
    #create an agent obj
    agent= Agent(working_dir)
    loop=asyncio.get_event_loop()
    try:
        #keep connection alive like persistent http
        while True:
            user_message= await websocket.receive_text()
            #necessary to have tool calls being shown since we need updates
            #trying to do this without asynchio results in errors
            def send_update(text: str):
                asyncio.run_coroutine_threadsafe(websocket.send_text(f"UPDATE:{text}"),loop)
            #run agent and send back result
            reply=agent.chat(user_message,verbose=False,on_update=send_update)
            #send reply back to extension
            await websocket.send_text(f"DONE:{reply}")
    except WebSocketDisconnect:
        print("Client Disconnected")

#decorator that tells fastapi to run this function before the first server starts sort of like a contrsutctor
@app.on_event("startup")
async def startup():
    print("Agent server running on ws://localhost:8000")

#this mkaes it so only running directly works and cant be run using import server or something from elsewhere
if __name__=="__main__":
    uvicorn.run(app,host="localhost",port=8000)


