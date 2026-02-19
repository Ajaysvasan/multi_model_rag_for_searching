import json
import os
import sys
from datetime import datetime
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)


def write_logs(log_type: str, start_time: float, end_time: float):
    """
    Writes performance logs to backend/logs/tui_perf.json line by line.

    Args:
        log_type (str): "init" or "last_query" or any other identifier.
        start_time (float): specific start timestamp
        end_time (float): specific end timestamp
    """
    duration = end_time - start_time

    # Determine logs directory relative to this file
    current_dir = Path(__file__).parent
    logs_dir = current_dir.parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_file = logs_dir / "tui_perf.json"

    log_entry = {
        "timestamp": datetime.fromtimestamp(end_time).isoformat() + "Z",
        log_type: {"total": round(duration, 4)},
    }

    try:
        with open(log_file, "w") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"Failed to write log: {e}")
