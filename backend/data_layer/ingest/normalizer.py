"""Normalize and preprocess extracted text"""

import re
from typing import Dict, Optional

NORMALIZATION_VERSION = "rag_v1"


class TextNormalizer:
    def __init__(
        self,
        lowercase: bool = True,
        remove_extra_whitespace: bool = True,
        remove_special_chars: bool = False,
        remove_numbers: bool = False,
        remove_punctuation: bool = False,
        remove_urls: bool = False,
        remove_emails: bool = False,
        remove_newlines: bool = False,
        strip_whitespace: bool = True,
    ):
        self.lowercase = lowercase
        self.remove_extra_whitespace = remove_extra_whitespace
        self.remove_special_chars = remove_special_chars
        self.remove_numbers = remove_numbers
        self.remove_punctuation = remove_punctuation
        self.remove_urls = remove_urls
        self.remove_emails = remove_emails
        self.remove_newlines = remove_newlines
        self.strip_whitespace = strip_whitespace

    def _replace_urls(self, text: str, placeholder: str = "[URL]") -> str:
        url_pattern = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        text = re.sub(url_pattern, placeholder, text)
        www_pattern = r"www\.(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        text = re.sub(www_pattern, placeholder, text)
        return text

    def _replace_emails(self, text: str, placeholder: str = "[EMAIL]") -> str:
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        return re.sub(email_pattern, placeholder, text)

    def _remove_numbers(self, text: str) -> str:
        return re.sub(r"\d+", "", text)

    def _remove_punctuation(self, text: str) -> str:
        return re.sub(r"[^\w\s]", "", text)

    def _remove_special_chars(self, text: str) -> str:
        return re.sub(r"[^a-zA-Z0-9\s.,!?;:\-\']", "", text)

    def _remove_extra_whitespace(self, text: str) -> str:
        return re.sub(r"\s+", " ", text)

    def _normalize_newlines(self, text: str) -> str:
        """Normalize newlines while preserving paragraph structure"""
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
        return text

    def normalize_text(self, text: str) -> str:
        if not text:
            return ""

        if self.remove_urls:
            text = self._replace_urls(text)

        if self.remove_emails:
            text = self._replace_emails(text)

        if self.remove_newlines:
            text = self._normalize_newlines(text)

        if self.lowercase:
            text = text.lower()
        if self.remove_numbers:
            text = self._remove_numbers(text)

        if self.remove_punctuation:
            text = self._remove_punctuation(text)

        if self.remove_special_chars:
            text = self._remove_special_chars(text)

        if self.remove_extra_whitespace:
            text = self._remove_extra_whitespace(text)

        if self.strip_whitespace:
            text = text.strip()

        return text

    def normalize_all(self, extracted_texts: Dict[str, str]) -> Dict[str, str]:
        normalized_texts = {}

        for file_path, text in extracted_texts.items():
            print(f"Normalizing: {file_path}")
            normalized_text = self.normalize_text(text)
            normalized_texts[file_path] = normalized_text

        return normalized_texts


class NormalizationProfiles:
    """Normalization configurations for different use cases"""

    @staticmethod
    def rag_ingestion():
        """
        Fixed policy for RAG ingestion - preserves semantic content while cleaning.

        This is the ONLY profile that should be used for ingesting documents into
        a RAG system. It:
        - Preserves case (important for named entities)
        - Replaces URLs/emails with placeholders (preserves context)
        - Normalizes newlines (preserves paragraph structure)
        - Removes extra whitespace
        - Does NOT remove punctuation, numbers, or special chars
        """
        return TextNormalizer(
            lowercase=False,
            remove_extra_whitespace=True,
            remove_urls=True,
            remove_emails=True,
            remove_newlines=True,
            remove_special_chars=False,
            remove_numbers=False,
            remove_punctuation=False,
            strip_whitespace=True,
        )

    @staticmethod
    def minimal():
        """Minimal cleaning - just trim whitespace (for custom pipelines)"""
        return TextNormalizer(
            lowercase=False,
            remove_extra_whitespace=True,
            strip_whitespace=True,
            remove_urls=False,
            remove_emails=False,
        )


if __name__ == "__main__":
    from pathlib import Path

    from Text_files_processing.file_loader import FileLoader
    from Text_files_processing.text_extractor import TextExtractor

    print(f"Using normalization version: {NORMALIZATION_VERSION}")

    data_path = str(Path.cwd() / "data" / "datasets")

    file_loader = FileLoader(data_path)
    loaded_files = file_loader.load_files()

    extractor = TextExtractor()
    extracted_texts = extractor.extract_all(loaded_files)

    # Use the fixed RAG ingestion policy
    normalizer = NormalizationProfiles.rag_ingestion()
    normalized_texts = normalizer.normalize_all(extracted_texts)

    for file_path, text in normalized_texts.items():
        print(f"File: {file_path}")
        print(f"Text length: {len(text)} characters")
        print(f"Preview: {text[:200]}...")

    # Example showing placeholder replacements
    sample_text = (
        "Contact us at support@example.com or visit https://example.com.\n\n"
        "Our office is at 123 Main St. Price: $99.99\n"
        "More info at www.docs.example.com"
    )
    print(f"\nOriginal:\n{sample_text}")
    print(f"\nNormalized:\n{normalizer.normalize_text(sample_text)}")
