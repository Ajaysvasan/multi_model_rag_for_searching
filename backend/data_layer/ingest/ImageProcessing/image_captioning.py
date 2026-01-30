# we need to caption the image because it makes the model to understand the image clearly
# we will also do visual embedding to capture the features of images 

import torch
from transformers import BlipProcessor, BlipForConditionalGeneration
from backend.data_layer.ingest.ImageProcessing.image_processing import ImagePreprocessor


class ImageCaptioner:
    def __init__(self, device=None):
        self.model = None
        self.processor = None
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

    def load_model(self):
        
        if self.model is not None:
            return

        self.processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")  # Preprocessing image
        self.model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base") # Caption Generator of image

        self.model.to(self.device)
        self.model.eval()

    @torch.no_grad()
    def generate_caption(self, image, max_length=50):
        
        self.load_model()

        inputs = self.processor(
            images=image,
            return_tensors="pt"
        ).to(self.device)

        output_ids = self.model.generate(
            **inputs,
            max_length=max_length,
            num_beams=5,
            early_stopping=True
        )

        caption = self.processor.decode(
            output_ids[0],
            skip_special_tokens=True
        )

        return caption.strip()

# file_directory = input("Enter a valid images file directory : ")
# images = ImagePreprocessor()

# captioning = ImageCaptioner()
# # Get the directory where images of users are stored and make it process.

# preprocessed_images = images.process_directory(file_directory)
# # [(img , src_path)  , (img , src_path) , ...]
# for img,filename in preprocessed_images:
    
#     caption = captioning.generate_caption(img)
#     print(caption)