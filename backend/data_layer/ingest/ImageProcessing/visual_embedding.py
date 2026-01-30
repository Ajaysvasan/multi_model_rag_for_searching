# Visual embedding 

import torch
import numpy as np
from transformers import CLIPProcessor, CLIPModel
from backend.data_layer.ingest.ImageProcessing.image_processing import ImagePreprocessor
from backend.data_layer.ingest.ImageProcessing.image_captioning import ImageCaptioner

class VisualEmbedder:
    def __init__(self, device=None):
        self.model = None
        self.processor = None
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

    def load_model(self):
        if self.model is not None:
            return

        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")

        self.model.to(self.device)
        self.model.eval()

    @torch.no_grad()
    def generate_embedding(self, image):

        self.load_model()

        inputs = self.processor(
            images=image,
            return_tensors="pt"
        ).to(self.device)

        image_features = self.model.get_image_features(**inputs)

        # Normalize for cosine similarity
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        return image_features[0].cpu().numpy()


if __name__ == "__main__":

    file_directory = input("Enter a valid images file directory : ")
    images = ImagePreprocessor()

    captioning = ImageCaptioner()
    visual_embedding = VisualEmbedder()
    # Get the directory where images of users are stored and make it process.

    preprocessed_images = images.process_directory(file_directory)
    # [(img , src_path)  , (img , src_path) , ...]
    for img,filename in preprocessed_images:
        
        captioner = captioning.generate_caption(img)

        visualEmbedding =visual_embedding.generate_embedding(img)
        print("Embedding for the image")
        print(visualEmbedding)

        print(captioner)

        print()