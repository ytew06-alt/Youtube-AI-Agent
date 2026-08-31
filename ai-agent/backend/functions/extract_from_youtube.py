import yt_dlp
from google.genai import types
import time
from gemini_client import call_gemini_retry
from gemini_client import call_with_fallback
from models import VIDEO_MODEL
import re
from config import CancelledByUser


def normalise_youtube_url(url:str) ->str:
    "Remove timestamp paramter from link for gemini compatability"
    patterns=[
        r"youtu\.be/([0-9A-Za-z_-]{11})",
        r"[?&]v=([0-9A-Za-z_-]{11})",

    ]
    for pattern in patterns:
        match=re.search(pattern,url)
        if match:
            return f"https://www.youtube.com/watch?v={match.group(1)}"
    raise ValueError(f"Could not extract a YouTube video ID from: {url}")


def get_video_duration(url:str):
    #opens up the YoutubeDL tool, quiet prevents bunch og logging text
    #skip dowload gives u only metadata and doesnt dowload video
    #saves this context manager as ydl
    
    """Returns duration in seconds, or None if YouTube blocks the request."""
    attempts = [
        {'quiet': True, 'skip_download': True, 'no_warnings': True},
        {'quiet': True, 'skip_download': True, 'no_warnings': True,
         'extractor_args': {'youtube': {'player_client': ['android']}}},
        {'quiet': True, 'skip_download': True, 'no_warnings': True,
         'extractor_args': {'youtube': {'player_client': ['ios']}}},
    ]
    for opts in attempts:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info.get('duration'):
                    return info.get('duration')
        except Exception as e:
            continue
    print(f"[youtube] duration lookup failed, falling back to whole-video mode")
    return None
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

def process_whole_video(client, url, on_update=None, cancel_event=None) -> str:
    """Used when duration is unknown. Gemini fetches and samples the entire
    video itself, so no local YouTube request is needed."""
    video_part = types.Part(
        file_data=types.FileData(file_uri=url),
        video_metadata=types.VideoMetadata(fps=0.5)
    )

    prompt = """You are watching a coding tutorial video.
Track all code visible in the editor as it is typed, edited, or scrolled — ignore the presenter's webcam if visible.
Output ONLY the code you observe. If multiple files are shown, separate them with a comment stating the filename.
Use narration audio to help confirm what's being typed when the visual is ambiguous.
If a moment involves fast scrolling or typing where you are NOT confident in the exact text, mark that spot with "# UNCERTAIN: <brief note>" instead of guessing."""

    print("\n>>> GEMINI REQUEST (whole video, no chunking)")
    response = call_with_fallback(
        client, on_update=on_update, cancel_event=cancel_event,
        model=VIDEO_MODEL,
        contents=[video_part, types.Part(text=prompt)],
        config=types.GenerateContentConfig(
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_MEDIUM
        )
    )
    return response.text

def process_chunk(client,url: str, start_sec: int, end_sec: int,on_update=None,cancel_event=None) -> str:
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
    response = call_with_fallback(
        client, on_update=on_update, cancel_event=cancel_event,
        model=VIDEO_MODEL,
        contents=[video_part, types.Part(text=prompt)],
        config=types.GenerateContentConfig(
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH
        )
    )
    return response.text


def merge_chunks(client,code_chunks:list[str],on_update=None, cancel_event=None):
    combined = "\n\n---CHUNK BOUNDARY---\n\n".join(code_chunks)
    prompt = f"""Below are code reconstructions from consecutive, slightly overlapping segments of the same coding tutorial video.
    Merge them into one final, clean, correct set of files. Remove duplicated code from the overlaps.
    Preserve any "# UNCERTAIN" markers so the user knows what to double check. {combined}"""
    print("\n>>> GEMINI REQUEST (YouTube chunk)")
    response = call_with_fallback(
        client,on_update=on_update,cancel_event=cancel_event,
        model=VIDEO_MODEL,
        contents=[types.Part(text=prompt)]
    )
    return response.text

# def extract_code_from_video(client,url:str,on_update=None,cancel_event=None):
#     url = normalise_youtube_url(url)
#     duration=get_video_duration(url)

#     chunks=get_chunks(duration) #list of tuples [(0,60),[55,115]] etc
#     code_chunks=[]

#     for i in range(len(chunks)):
#         start,end=chunks[i]
#         if cancel_event is not None and cancel_event.is_set():
#             raise CancelledByUser()
  
#         #gives real time updates if needed
#         if on_update:
#             on_update(f"Processing chunk {i+1}/{len(chunks)}({start}s - {end}s)...")
#         #essentially calls the gemini API and gets the extracted code
#         result=process_chunk(client,url,start,end,on_update=on_update)
#         code_chunks.append(result)
#         if i<len(chunks) -1:
#             #prevents exceedint tokens per minute restriction
#             time.sleep(65) 
#     if len(code_chunks)==1:
#         return code_chunks[0]
#     return merge_chunks(client,code_chunks,on_update=on_update,cancel_event=cancel_event)


def extract_code_from_video(client, url: str, on_update=None, cancel_event=None):
    url = normalise_youtube_url(url)
    duration = get_video_duration(url)

    if duration is None:
        if on_update:
            on_update("Couldn't read video length — processing the whole video in one pass...")
        return process_whole_video(client, url, on_update=on_update, cancel_event=cancel_event)

    chunks = get_chunks(duration)
    code_chunks = []

    for i, (start, end) in enumerate(chunks):
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledByUser()
        if on_update:
            on_update(f"Processing chunk {i+1}/{len(chunks)} ({start}s - {end}s)...")
        code_chunks.append(process_chunk(client, url, start, end,
                                         on_update=on_update, cancel_event=cancel_event))
        if i < len(chunks) - 1:
            wait_or_cancel(65, cancel_event)

    if len(code_chunks) == 1:
        return code_chunks[0]
    return merge_chunks(client, code_chunks, on_update=on_update, cancel_event=cancel_event)


def wait_or_cancel(seconds, cancel_event):
    for i in range(seconds):
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledByUser()
        time.sleep(1)


#this is used if yt dlp gives cookie er