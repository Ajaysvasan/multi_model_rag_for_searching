"""Normalizer module"""

from pathlib import Path

from Text_files_processing.file_loader import FileLoader
from Text_files_processing.text_extractor import TextExtractor


class Normalizer:
    """For each file (source path) normalize the text and store them in the dict in the following format"""

    def __init__(self) -> None:
        pass


if __name__ == "__main__":
    data_path = str(Path.cwd() / "data" / "datasets")
    text_extractor = TextExtractor()
    file_loader = FileLoader(data_path)

    loaded_files = file_loader.load_files()

    print(type(text_extractor.extract_all(loaded_files)))
