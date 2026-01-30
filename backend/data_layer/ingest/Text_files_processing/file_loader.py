import os
from pathlib import Path
from typing import Dict, List


class FileLoader:
    def __init__(self, folder_path: str = "") -> None:
        self.folder_path = folder_path
        self.allowed_extensions = {".doc", ".docx", ".txt", ".pdf"}

    def _is_directory(self, path: str) -> bool:
        """Check if the given path is a directory"""
        return os.path.isdir(path)

    def _get_file_category(self, file_path: str) -> str:
        """Determine the category of a file based on its extension"""
        extension = Path(file_path).suffix.lower()

        if extension in {".doc", ".docx"}:
            return "docs"
        elif extension == ".txt":
            return "txt"
        elif extension == ".pdf":
            return "pdf"
        return None

    def _scan_directory(
        self, directory: str, loaded_files: Dict[str, List[str]]
    ) -> None:
        """Recursively scan directory and categorize files"""
        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)

                if self._is_directory(item_path):
                    # Recursively scan subdirectories
                    self._scan_directory(item_path, loaded_files)
                else:
                    # Check if file has allowed extension
                    extension = Path(item_path).suffix.lower()
                    if extension in self.allowed_extensions:
                        category = self._get_file_category(item_path)
                        if category:
                            loaded_files[category].append(item_path)
        except PermissionError:
            print(f"Permission denied: {directory}")
        except Exception as e:
            print(f"Error scanning {directory}: {e}")

    def load_files(self) -> Dict[str, List[str]]:
        """
        The output will be in the following format:
        {
            'docs': [file_one_path, file_path_two, ...],
            'pdf': [file_one_path, file_path_two],
            'txt': [file_one_path, ...]
        }
        """
        loaded_files = {"docs": [], "txt": [], "pdf": []}

        if not self.folder_path:
            print("Warning: No folder path provided")
            return loaded_files

        if not os.path.exists(self.folder_path):
            print(f"Error: Path does not exist: {self.folder_path}")
            return loaded_files

        if not self._is_directory(self.folder_path):
            print(f"Error: Path is not a directory: {self.folder_path}")
            return loaded_files

        # Recursively scan the directory
        self._scan_directory(self.folder_path, loaded_files)

        return loaded_files


if __name__ == "__main__":

    data_path = str(Path.cwd() / "data" / "datasets")
    file_loader = FileLoader(data_path)
    print(file_loader.load_files())
