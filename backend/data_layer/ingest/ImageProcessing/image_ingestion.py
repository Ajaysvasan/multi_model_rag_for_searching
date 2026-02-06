from image_processing import ImagePreprocessor
from image_captioning import ImageCaptioner
from ocr_processing import OCRProcessor
from visual_embedding import VisualEmbedder
from metadata_extracter import MetadataExtractor


# file_directory = input("Enter a valid images file directory: ")
# Input will be coming from another function which is linked with frontend.. 

def ingest_image(file_directory: str):

    # Initialize processors
    image_processor = ImagePreprocessor()
    captioner = ImageCaptioner()
    ocr = OCRProcessor()
    visual_embedder = VisualEmbedder()
    metadata_extractor = MetadataExtractor()

    results = []

    # Loading & preprocessing images
    preprocessed_images = image_processor.process_directory(file_directory)

    for img, image_path in preprocessed_images:

        # OCR processing

        ocr_result = ocr.extract_text(img)
        has_text = bool(ocr_result["text"])

        # simple image-type detector
        image_type = "screenshot" if has_text else "photo"

        # Caption generator function for generating caption for the given image
        caption = captioner.generate_caption(img)

        # Visual embedding  function for the given image
        image_embedding = visual_embedder.generate_embedding(img)

        # Metadata extraction function for extraction of meta data from the image
        metadata = metadata_extractor.extract_metadata(
            image_path=image_path,
            image=img,
            has_text=has_text,
            image_type=image_type,
            caption=caption
        )

        record = {
            "embedding": image_embedding,
            "metadata": metadata,
            "ocr_text": ocr_result["text"]
        }

        results.append(record)
    return results