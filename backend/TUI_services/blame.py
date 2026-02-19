import json
from pathlib import Path


def blame_command():
    try:
        current_dir = Path(__file__).parent
        logs_dir = current_dir.parent / "logs"
        log_file = logs_dir / "tui_perf.json"
        with open(log_file, "r", encoding="utf-8") as file:
            data = json.load(file)
        print(data)
    except Exception as e:
        print(f"The Following exception occured {e}")
