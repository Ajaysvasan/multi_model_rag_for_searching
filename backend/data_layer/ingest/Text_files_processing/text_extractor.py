import os
from pathlib import Path
from typing import Dict


class TextExtractor:
    def __init__(self):
        """Initialize the text extractor"""
        pass

    def _extract_from_txt(self, file_path: str) -> str:
        """Extract text from a .txt file"""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, "r", encoding="latin-1") as file:
                    return file.read()
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                return ""
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return ""

    def _extract_from_docx(self, file_path: str) -> str:
        """Extract text from a .docx file"""
        try:
            from docx import Document

            doc = Document(file_path)
            full_text = []
            for paragraph in doc.paragraphs:
                full_text.append(paragraph.text)
            return "\n".join(full_text)
        except ImportError:
            print(
                "Error: python-docx library not installed. Run: pip install python-docx"
            )
            return ""
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return ""

    def _extract_from_doc(self, file_path: str) -> str:
        """Extract text from a .doc file (legacy format)"""
        try:
            import textract

            text = textract.process(file_path).decode("utf-8")
            return text
        except ImportError:
            print("Error: textract library not installed. Run: pip install textract")
            print("Note: textract may require additional system dependencies")
            return ""
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return ""

    def _extract_from_pdf(self, file_path: str) -> str:
        """Extract text from a .pdf file"""
        try:
            import PyPDF2

            text = []
            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text.append(page.extract_text())
            return "\n".join(text)
        except ImportError:
            print("Error: PyPDF2 library not installed. Run: pip install PyPDF2")
            return ""
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return ""

    def extract_text_from_file(self, file_path: str) -> str:
        """Extract text from a single file based on its extension"""
        if not os.path.exists(file_path):
            print(f"Error: File does not exist: {file_path}")
            return ""

        extension = Path(file_path).suffix.lower()

        if extension == ".txt":
            return self._extract_from_txt(file_path)
        elif extension == ".docx":
            return self._extract_from_docx(file_path)
        elif extension == ".doc":
            return self._extract_from_doc(file_path)
        elif extension == ".pdf":
            return self._extract_from_pdf(file_path)
        else:
            print(f"Unsupported file type: {extension}")
            return ""

    def extract_all(self, loaded_files: Dict[str, list]) -> Dict[str, str]:
        """
        Extract text from all files returned by FileLoader.

        Args:
            loaded_files: Dictionary with format {'docs': [...], 'txt': [...], 'pdf': [...]}

        Returns:
            Dictionary with format {source_file_path: "extracted_text", ...}
        """
        extracted_texts = {}

        for category, file_paths in loaded_files.items():
            for file_path in file_paths:
                print(f"Processing: {file_path}")
                text = self.extract_text_from_file(file_path)
                extracted_texts[file_path] = text

        return extracted_texts


if __name__ == "__main__":
    from file_loader import FileLoader

    data_path = str(Path.cwd() / "data" / "datasets")
    file_loader = FileLoader(data_path)
    loaded_files = file_loader.load_files()

    print(f"Found files: {loaded_files}")
    print("\n" + "=" * 50 + "\n")

    extractor = TextExtractor()
    extracted_texts = extractor.extract_all(loaded_files)

    for file_path, text in extracted_texts.items():
        print(f"File: {file_path}")
        print(f"Text length: {len(text)} characters")
        print(f"Preview: {text[:200]}...")
