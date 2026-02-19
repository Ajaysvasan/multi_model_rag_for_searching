#!/usr/bin/env python3
import argparse
import os
import sys
import time
from pathlib import Path

from TUI_services.logger import write_logs
from TUI_services.start import start


class InvalidCommand(Exception):
    """Exception raised for invlaid commad"""

    def __init__(self, message="The command not found") -> None:
        self.message = message
        super().__init__(f"{self.message} ")


def find_path(dir_name: str = "", root_path: str = ""):
    root = Path(root_path)
    for path in root.rglob("*"):
        if path.is_dir() and path.name == dir_name:
            return path.absolute()
    return None


def main():
    parser = argparse.ArgumentParser(description="TUI starter")
    subparser = parser.add_subparsers(dest="command", help="avaliable commands")
    subparser.add_parser("start", help="To start the AI and interact with it")
    ingest_parser = subparser.add_parser(
        "ingest",
        help="To insert new data for the model by default it looks in all the directories for all the files",
    )
    ingest_parser.add_argument(
        "--path",
        type=str,
        help="To ingest file / files that are in a specific directories",
    )
    subparser.add_parser(
        "blame",
        help="To see the time taken by the system to initialize and execute a task.\nThe system must have been run atleast one time",
    )
    subparser.add_parser("clear", help="This command clears the data. ")
    try:
        args = parser.parse_args()
        match (args.command):
            case "start":
                path = "/home"
                target_dir = "multi_model_rag_for_searching"
                directory_path = find_path(dir_name=target_dir, root_path=path)

                directory_path = Path(directory_path) / "backend"
                sys.path.append(str(directory_path))
                start()

            case "ingest":
                pass
            case "blame":
                pass
            case "clear":
                pass

    except Exception as e:
        raise Exception(f"The following exception has occured {e}")


if __name__ == "__main__":

    main()
