#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path


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
    parser.add_argument("start", type=str, help="To get use the agent using TUI")
    parser.add_argument(
        "ingest",
        type=str,
        help="To insert new data for the agent. If the name of the file or folder left empty then all the files will be taken as data",
    )
    parser.add_argument("clear", type=str, help="To clear all the data.")
    try:
        args = parser.parse_args()
        if args.start:
            path = "/home"
            target_dir = "multi_model_rag_for_searching"
            directory_path = find_path(dir_name=target_dir, root_path=path)

            directory_path = Path(directory_path) / "backend"
            sys.path.append(str(directory_path))
            from TUI_pipeline import pipeline

            pipeline()
        else:
            raise InvalidCommand()

    except Exception as e:
        raise Exception(f"The following exception has occured {e}")


if __name__ == "__main__":

    main()
