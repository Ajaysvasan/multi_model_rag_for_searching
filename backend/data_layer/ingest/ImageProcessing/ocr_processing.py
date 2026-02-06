import os
import cv2
import numpy as np
from PIL import Image
import pytesseract
from image_processing import ImagePreprocessor


# Main OCR Processor
class OCRProcessor:
    def __init__(self, lang='eng'):

        self.lang = lang
        self._verify_tesseract()

    def _verify_tesseract(self):
        
        try:
            version = pytesseract.get_tesseract_version()
            if version:
                return True
        except Exception as e:
            raise Exception(f"Tesseract not installed: {e}")

    def has_text(self, image: Image.Image, threshold=0.01) -> bool:
        # Checks whether the given image contains text or not.
        gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        edge_density = np.sum(edges > 0) / edges.size

        return edge_density > threshold

    def extract_text(self, image: Image.Image, config='--psm 3'):
       # Extraction of text from the image
        try:
            image_np = np.array(image)

            # Normalise to 3-channel RGB so Tesseract is happy
            if len(image_np.shape) == 2:                # grayscale
                image_np = cv2.cvtColor(image_np, cv2.COLOR_GRAY2RGB)
            elif image_np.shape[2] == 4:                # RGBA
                image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2RGB)

            # Detailed per-word data (includes confidence per word)
            ocr_data = pytesseract.image_to_data(
                image_np,
                lang=self.lang,
                config=config,
                output_type=pytesseract.Output.DICT,
            )

            # Full-page text string
            full_text = pytesseract.image_to_string(
                image_np,
                lang=self.lang,
                config=config,
            )

            # Average confidence — Tesseract uses -1 for non-word rows; filter those out
            confidences = [
                float(c) for c in ocr_data['conf']
                if c != -1 and c != '-1'
            ]
            avg_confidence = np.mean(confidences) if confidences else 0.0

            # Per-word details with bounding boxes
            word_details = []
            for i in range(len(ocr_data['text'])):
                if int(ocr_data['conf'][i]) > 0:
                    word_details.append({
                        'text':       ocr_data['text'][i],
                        'confidence': float(ocr_data['conf'][i]),
                        'bbox': (
                            ocr_data['left'][i],
                            ocr_data['top'][i],
                            ocr_data['width'][i],
                            ocr_data['height'][i],
                        ),
                    })

            return {
                "text":         full_text.strip(),
                "confidence":   avg_confidence / 100.0,   # scale to 0–1
                "word_details": word_details,
            }

        except Exception as e:
            print(f"OCR Error: {e}")
            return {
                "text":         "",
                "confidence":   0.0,
                "word_details": [],
            }

    def extract_text_enhanced(self, image: Image.Image):
        
        img_np = np.array(image)

        # Convert to single-channel grayscale
        if len(img_np.shape) == 3:
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_np

        # Otsu binarisation — automatically picks the best threshold
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Median filter to remove salt-and-pepper noise
        denoised = cv2.medianBlur(binary, 3)

        preprocessed = Image.fromarray(denoised)
        return self.extract_text(preprocessed)


if __name__ == "__main__":

    file_directory = input("Enter a valid images file directory: ")

    # Initialize processors
    images = ImagePreprocessor()
    ocr_processor = OCRProcessor(lang='eng')  # Use 'eng' for English

    # Process images
    preprocessed_images = images.process_directory(file_directory)

    for img, filename in preprocessed_images:

        if not ocr_processor.has_text(img): # Checks every image whether they contain text or not
            # If no text it skip that image and proceed with next image
            # else it will start to extract the text from the image....

            print("No text in image \n Proceeds with next image")
            continue

        # Extract text
        ocr_result = ocr_processor.extract_text(img)

        print(f" Confidence: {ocr_result['confidence']:.2%}")
        print(f" Words detected: {len(ocr_result['word_details'])}")

        if ocr_result['text']:
            print("\n Extracted Text:")
            print(ocr_result["text"])
            print()

            # Show top 5 words with confidence
            if ocr_result['word_details']:
                print("\n Sample word confidences:")
                for word_info in ocr_result['word_details'][:5]:
                    print(f"   '{word_info['text']}' - {word_info['confidence']:.1f}%")
        else:
            print("No text extracted from image")