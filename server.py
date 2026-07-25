from fastapi import FastAPI, WebSocket,WebSocketDisconnect,Query
from agent_class import Agent
import uvicorn
import asyncio
import json
import traceback
#The main thing this does is that norammly u wud write terminal command
#That terminal command wud run python load history load cache load agemt and everything
#using fastapi and websockets the connection opens and these things remain open for infinite requests
#till the server is closed

app=FastAPI()
LOCAL_TOKEN="hidden_dev_token"

#websocket endpoint
@app.websocket("/chat")
async def chat_endpoint(websocket: WebSocket, token: str= Query(None)):
    if token!= LOCAL_TOKEN:
        #block invalid connections
        await websocket.close(code=1008,reason="Invalid Token")
        return

    #handshake to open the connection
    await websocket.accept()
    try:
        #wait for auth payload
        first_message= await websocket.receive_text()
        try:
            auth_data=json.loads(first_message)
            api_key=auth_data.get("api_key")

            if not api_key:
                raise ValueError("No API key found in payload")

        except (json.JSONDecodeError,ValueError):
            await websocket.close(code=1008,reason="Authetication failed")
            return

        #get the working directory input from the extension
        working_dir= await websocket.receive_text()
        #create an agent obj
        agent= Agent(working_dir,api_key=api_key)
        loop=asyncio.get_event_loop()
        #keep connection alive like persistent http
        while True:
            user_message= await websocket.receive_text()
            #necessary to have tool calls being shown since we need updates
            #trying to do this without asynchio results in errors
            def send_update(text: str):
                asyncio.run_coroutine_threadsafe(websocket.send_text(f"UPDATE:{text}"),loop)
            #run agent and send back result, but dont let one bad reply kill the whole socket
            try:
                reply=agent.chat(user_message,verbose=False,on_update=send_update)
                await websocket.send_text(f"DONE:{reply}")
            except Exception as e:
                print(f"Chat error: {e}")
                await websocket.send_text(f"DONE:Error - {str(e)}")

    except WebSocketDisconnect:
        print("Client Disconnected")
    except Exception as e:
        print(f"Unexpected Server Error: {e}")
        try:
            await websocket.send_text(f"Error:{str(e)}")
        except Exception as e:
            print(f"Chat error: {e}")
            traceback.print_exc()
            await websocket.send_text(f"DONE:Error - {str(e)}")

            pass

#decorator that tells fastapi to run this function before the first server starts sort of like a contrsutctor
@app.on_event("startup")
async def startup():
    print("Agent server running on ws://localhost:8000")

#this mkaes it so only running directly works and cant be run using import server or something from elsewhere
if __name__=="__main__":
    uvicorn.run(app,host="localhost",port=8000)