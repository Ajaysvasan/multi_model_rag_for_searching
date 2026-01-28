"""To load the data / files from the given folder"""

import os


class FileLoader:
    def __init__(self, folder_path: str = "") -> None:
        self.folder_path = folder_path

    def _get_types_file_extension(self):
        # This gives me the file extension so that if the file has a mixed file in a single folder
        # So that we can indentify them segerate them in a way that we can pass that to the exact text loader that we want
        extentions = []
        return extentions

    def load_files(self):
        """The output will be in the following format {'docs' : [file_one_path , file_path_two , ...] , 'pdf': [file_one_path,file_path_two] , 'txt':[file_one_path , ...]}"""
        loaded_files = dict()
        return loaded_files


if __name__ == "__main__":
    file_loader = FileLoader()
    print(file_loader.load_files())
