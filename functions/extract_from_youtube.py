import yt_dlp
from google.genai import types
import time
from gemini_client import call_gemini_retry
from models import VIDEO_MODEL
from gemini_client import call_with_fallback

def get_video_duration(url:str):
    #opens up the YoutubeDL tool, quiet prevents bunch og logging text
    #skip dowload gives u only metadata and doesnt dowload video
    #saves this context manager as ydl
    with yt_dlp.YoutubeDL({'quiet':True,'skip_download':True}) as ydl:
        #info is a dict and extract info gives title,author,views etc
        info=ydl.extract_info(url,download=False)
        return info['duration']
CHUNK_THRESHOLD=900 #15 MINS
CHUNK_SIZE=300
OVERLAP=20 #20s so code isnt lost between chunka

def get_chunks(duration:int):
    #check is entire video is shorter than a chunk and returns entire video as a chunk
    if duration<=CHUNK_THRESHOLD:
        return [(0,duration)]
    chunks=[]
    start=0
    while start<duration:
        #prevents overshooting with chunk duration and caps it at duration of video
        end=min(start+CHUNK_SIZE,duration)
        chunks.append((start,end))
        if end >= duration:
            break
        #the next start is now at the last chunks end for overlap
        start=end-OVERLAP
    return chunks


def process_chunk(client,url: str, start_sec: int, end_sec: int) -> str:
    #use part instead of content since content packages multiple parts
    video_part = types.Part(
        file_data=types.FileData(file_uri=url),
        video_metadata=types.VideoMetadata(
            start_offset=f"{start_sec}s",
            end_offset=f"{end_sec}s",
            fps=0.5
        )
    )

    prompt = f"""You are watching a segment of a coding tutorial video, from {start_sec}s to {end_sec}s.
Track all code visible in the editor as it is typed, edited, or scrolled — ignore the presenter's webcam if visible.
Output ONLY the code you observe. If multiple files are shown, separate them with a comment stating the filename (infer it from tabs/title bar if visible).
Use narration audio to help confirm what's being typed when the visual is ambiguous.
If a moment involves fast scrolling or typing where you are NOT confident in the exact text, mark that spot with "# UNCERTAIN: <brief note>" instead of guessing convincing-looking but possibly wrong code."""
    print("\n>>> GEMINI REQUEST (YouTube chunk)")
    response = call_gemini_retry(
        client,
        model=VIDEO_MODEL,
        contents=[video_part, types.Part(text=prompt)],
        config=types.GenerateContentConfig(
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH
        )
    )
    return response.text


def merge_chunks(client,code_chunks:list[str]):
    combined = "\n\n---CHUNK BOUNDARY---\n\n".join(code_chunks)
    prompt = f"""Below are code reconstructions from consecutive, slightly overlapping segments of the same coding tutorial video.
    Merge them into one final, clean, correct set of files. Remove duplicated code from the overlaps.
    Preserve any "# UNCERTAIN" markers so the user knows what to double check. {combined}"""
    print("\n>>> GEMINI REQUEST (YouTube chunk)")
    response = call_with_fallback(
        client,
        model=VIDEO_MODEL,
        contents=[types.Part(text=prompt)]
    )
    return response.text

def extract_code_from_video(client,url:str,on_update=None):
    duration=get_video_duration(url)

    chunks=get_chunks(duration) #list of tuples [(0,60),[55,115]] etc
    code_chunks=[]

    for i in range(len(chunks)):
        start,end=chunks[i]
  
        #gives real time updates if needed
        if on_update:
            on_update(f"Processing chunk {i+1}/{len(chunks)}({start}s - {end}s)...")
        #essentially calls the gemini API and gets the extracted code
        result=process_chunk(client,url,start,end)
        code_chunks.append(result)
        if i<len(chunks) -1:
            #prevents exceedint tokens per minute restriction
            time.sleep(65) 
    if len(code_chunks)==1:
        return code_chunks[0]
    return merge_chunks(client,code_chunks)

