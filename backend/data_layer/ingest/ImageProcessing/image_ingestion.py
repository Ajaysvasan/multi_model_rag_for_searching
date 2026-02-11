import os
import sys
import hashlib

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from image_processing import ImagePreprocessor
from image_captioning import ImageCaptioner
from ocr_processing import OCRProcessor
from metadata_extracter import MetadataExtractor


def ingest_images(file_paths: list) -> list:
    preprocessor = ImagePreprocessor()
    captioner = ImageCaptioner()
    metadata_extractor = MetadataExtractor()

    try:
        ocr = OCRProcessor()
    except Exception:
        ocr = None

    records = []

    for image_path in file_paths:
        try:
            img = preprocessor.preprocess_image(image_path)
            caption = captioner.generate_caption(img)

            ocr_text = ""
            if ocr is not None:
                try:
                    ocr_result = ocr.extract_text(img)
                    ocr_text = ocr_result.get("text", "")
                except Exception:
                    pass

            has_text = bool(ocr_text.strip())
            image_type = "screenshot" if has_text else "photo"

            chunk_text = f"[Image: {caption}]"
            if ocr_text.strip():
                chunk_text += f"\n{ocr_text.strip()}"

            abs_path = str(os.path.abspath(image_path))
            doc_id = hashlib.sha256(abs_path.encode()).hexdigest()
            chunk_id = hashlib.sha256(f"{doc_id}|image|0".encode()).hexdigest()[:16]

            metadata = metadata_extractor.extract_metadata(
                image_path=image_path,
                image=img,
                has_text=has_text,
                image_type=image_type,
                caption=caption,
            )

            records.append({
                "chunk_id": chunk_id,
                "document_id": doc_id,
                "source_path": abs_path,
                "modality": "image",
                "chunk_index": 0,
                "start_offset": 0,
                "end_offset": len(chunk_text),
                "chunk_text": chunk_text,
                "metadata": metadata,
            })

            print(f"  [image] {os.path.basename(image_path)}: \"{caption[:80]}\"")

        except Exception as e:
            print(f"  [image] SKIP {image_path}: {e}")

    return records