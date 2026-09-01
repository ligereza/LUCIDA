import json
from pathlib import Path

def load_gold(path: str | Path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
