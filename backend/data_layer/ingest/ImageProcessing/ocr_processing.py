# OCR processing module
# Uses Tesseract OCR for completely offline text extraction

import os
import cv2
import numpy as np
from PIL import Image
import pytesseract
from image_processing import ImagePreprocessor



class OCRProcessor:
    def __init__(self, lang='eng'):
        
        self.lang = lang
        self._verify_tesseract()

    def _verify_tesseract(self):
        
        try:
            version = pytesseract.get_tesseract_version()
            print(f" Tesseract OCR v{version} found - Running in OFFLINE mode")
        except Exception as e:
            print("Tesseract OCR not found!")
            print("\nPlease install Tesseract OCR:")
            print("Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
            print("Linux: sudo apt-get install tesseract-ocr")
            print("macOS: brew install tesseract")
            raise Exception(f"Tesseract not installed: {e}")


    def has_text(self, image: Image.Image, threshold=0.01) -> bool:
        
        # This is a boolean function to check whether the image contains text or not which make the OCR to skip the image without text

        gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        edge_density = np.sum(edges > 0) / edges.size

        return edge_density > threshold

    
    def extract_text(self, image: Image.Image, config='--psm 3'):
        
        # Text extraction from the image which will be done by OCR
        
        try:
            # Convert PIL Image to numpy array
            image_np = np.array(image)
            
            # Ensure it's in RGB format if not convert the image to RGB
            if len(image_np.shape) == 2:  # Grayscale
                image_np = cv2.cvtColor(image_np, cv2.COLOR_GRAY2RGB)
            elif image_np.shape[2] == 4:  # RGBA
                image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2RGB)

            # Get detailed OCR data including confidence
            ocr_data = pytesseract.image_to_data(
                image_np,
                lang=self.lang,
                config=config,
                output_type=pytesseract.Output.DICT
            )
            
            # Extracting text from the image
            full_text = pytesseract.image_to_string(
                image_np,
                lang=self.lang,
                config=config
            )
            
            # Calculate average confidence (filter out -1 values)
            confidences = [
                float(conf) for conf in ocr_data['conf'] 
                if conf != -1 and conf != '-1'
            ]
            avg_confidence = np.mean(confidences) if confidences else 0.0
            
            # Get word-level details
            word_details = []
            n_boxes = len(ocr_data['text'])
            for i in range(n_boxes):
                if int(ocr_data['conf'][i]) > 0:  # Only include valid detections
                    word_details.append({
                        'text': ocr_data['text'][i],
                        'confidence': float(ocr_data['conf'][i]),
                        'bbox': (
                            ocr_data['left'][i],
                            ocr_data['top'][i],
                            ocr_data['width'][i],
                            ocr_data['height'][i]
                        )
                    })
            
            return {
                "text": full_text.strip(),
                "confidence": avg_confidence / 100.0,  # Convert to 0-1 range
                "word_details": word_details
            }
            
        except Exception as e:
            print(f" OCR Error: {e}")
            return {
                "text": "",
                "confidence": 0.0,
                "word_details": []
            }


    def extract_text_enhanced(self, image: Image.Image):
       
        # Convert to numpy array
        img_np = np.array(image)
        
        # Convert to grayscale
        if len(img_np.shape) == 3:
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_np
        
        # Apply preprocessing techniques
        # 1. Thresholding
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 2. Noise removal
        denoised = cv2.medianBlur(binary, 3)
        
        # Convert back to PIL Image
        preprocessed = Image.fromarray(denoised)
        
        # Run OCR on preprocessed image
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
            print("⚠️ No text extracted from image")