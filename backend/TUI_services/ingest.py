import os
import platform
import sys
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

sys.path.append(parent_dir)


def ingest_command(path_flag=False):
    if not path_flag:
        root_dir = Path.cwd().anchor
        if platform.system().lower() == "linux":
            root_dir = Path(root_dir) / "home"
        print(root_dir)


if __name__ == "__main__":
    ingest_command()
