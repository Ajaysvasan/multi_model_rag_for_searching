import os
import sys
from pathlib import Path

# Setup path to import config
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from config import Config


def clear_data():
    print("CLEARING LOCAL DATA")

    def get_path(p):
        if not p:
            return None
        return Path(p).resolve()

    files_to_delete = [
        get_path(Config.INDEX_PATH),
        get_path(str(Config.INDEX_PATH) + ".ids"),
        get_path(Config.METADATA_DB_PATH),
        get_path(Config.CACHE_HISTORY_DB_PATH),
        (
            get_path(Config.DB_PATH)
            if Config.DB_PATH != str(Config.CACHE_HISTORY_DB_PATH)
            else None
        ),
        get_path(Config.METADATA_PATH) if hasattr(Config, "METADATA_PATH") else None,
    ]

    deleted_count = 0

    for file_path in files_to_delete:
        if file_path and file_path.exists():
            try:
                os.remove(file_path)
                print(f"  [✓] Deleted: {file_path}")
                deleted_count += 1
            except Exception as e:
                print(f"  [✗] Error deleting {file_path}: {e}")

    if deleted_count == 0:
        print("  No data files found to delete.")
    else:
        print(f"\n  Successfully deleted {deleted_count} data file(s).")


if __name__ == "__main__":
    clear_data()
