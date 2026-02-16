"""Main module which will be integrated with the frontend"""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import platform
import threading

from config import Config
from system_init import initialize_system


def main():
    if platform.system().lower() not in Config.OS:
        raise OSError(
            f"The operating system {platform.system()} is not supported. Supporated Os list : {Config.OS}"
        )

    if platform.system().lower() == "windows":
        engine, metadata_store, conv_memory, session_id, query_preprocessor = (
            initialize_system()
        )
        model_thread = None  # responsible for loading the model in the memory
        pass
    else:
        # These are for linux
        pass


if __name__ == "__main__":
    main()
