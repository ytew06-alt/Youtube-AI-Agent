AGENT_MODEL      = "gemini-3.1-flash-lite"       # reasoning + tool use
SUMMARY_MODEL    = "gemini-3.1-flash-lite"  # compression, cheap
VIDEO_MODEL      = "gemini-3.1-flash-lite"  # chunk OCR, many requests

FALLBACK_CHAIN = {
    "gemini-3.1-flash-lite": ["gemini-3.1-flash"],
    "gemini-3.1-flash": ["gemini-3.1-flash-lite"],
}

MODEL_LIMITS = {
    "gemini-3.5-flash": {"rpm": 5, "rpd": 20},
    "gemini-3.1-flash-lite": {"rpm": 15, "rpd": 1000},
}
 
DEFAULT_LIMITS = {"rpm": 5, "rpd": 20}
 
# Keep a couple of requests in reserve so you never hard stop mid task.
RPD_SAFETY_MARGIN = 2