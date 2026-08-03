# diagnose_youtube.py
from google import genai
from google.genai import types
import os

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
url = "https://www.youtube.com/watch?v=BX6_YBPr7Jw"

video_part = types.Part(
    file_data=types.FileData(file_uri=url),
    video_metadata=types.VideoMetadata(start_offset="0s", end_offset="30s", fps=0.5)
)

for model in ["gemini-3.1-flash-lite", "gemini-3.5-flash"]:
    print(f"\n--- {model} ---")
    try:
        r = client.models.generate_content(model=model, contents=[video_part, types.Part(text="What do you see?")])
        print("SUCCESS:", r.text[:150])
    except Exception as e:
        print("FAILED:", e)