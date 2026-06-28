# calculator/pkg/render.py

import json


def format_json_output(data: dict, indent: int = 2) -> str:
    return json.dumps(data, indent=indent)