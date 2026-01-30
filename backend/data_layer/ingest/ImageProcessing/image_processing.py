# This is an image processing file.

# Importing libraries

from PIL import Image, ImageEnhance
import os

class ImagePreprocessor:
    def __init__(self):
        self.supported_formats = {'jpg', 'jpeg', 'png'}
        self.max_dimension = 1024
        self.min_dimension = 32
        self.standard_size = 384, 384

    def process_directory(self, dir_path):
        print("Inside process directry: ")
        processed_files = []

        for filename in os.listdir(dir_path):
            full_path = os.path.join(dir_path, filename)

            if not os.path.isfile(full_path):
                continue

            is_valid, error = self.validate_image(full_path)
            if not is_valid:
                print(f"Skipping {filename}: {error}")
                continue

            img = self.preprocess_image(full_path)

            # img.save(output_path)
            # Don't want to save the images as we don't want processed image to be shown.
            processed_files.append((img, full_path))

        return processed_files
    
    
    def preprocess_image(self, image_path):
        print("inside process image")
        with Image.open(image_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")

            img = img.resize(self.standard_size)
            print(img.size)
            # print(type(img))
            
            brightness_enhancer = ImageEnhance.Brightness(img)
            img = brightness_enhancer.enhance(3.0) # It enhance all the 3 colors Red, Green, Blue

            # As we are using contrast below we can enhance the color above.
            print("Colour enhanced")


            # contrast_enhancer = ImageEnhance.Contrast(img)
            # img = contrast_enhancer.enhance(1.5) 
            # as we use contrast here it will make the brighter part of image even brighter and darker spot even darker
            # Increase contrast by 50%
            # So dont want to use brightness enhancer......
            # print("Contrast enhanced")

            sharpness_enhancer = ImageEnhance.Sharpness(img)
            img = sharpness_enhancer.enhance(1.5)
            # increase sharpness by 50%

            print("Sharapness enhanced")

            image_copy = img.copy()
            return image_copy
        

    def validate_image(self, image_path):

        # Validate if image is usable.
        
        #if not os.path.exists(image_path): # Checking the path of the image
            # return False, "File does not exist"

        # extension = os.path.splitext(image_path)[1].lower()  # Check whether the given image is in supported format
        extension = image_path.split(".")[-1]
        print(f"extension = {extension}")
        if extension not in self.supported_formats:
            return False, f"Unsupported format: {extension}"

        try:
            with Image.open(image_path) as img:
                width, height = img.size
                if width < self.min_dimension or height < self.min_dimension:
                    return False, "Image too small to process"
        except Exception:
            return False, "Corrupted or unreadable image"

        return True, None


# if __name__ == "__main__":
#     file_directory = input("Enter a valid images file directory : ")
#     images = ImagePreprocessor()

#     # Get the directory where images of users are stored and make it process.

#     preprocessed_images = images.process_directory(file_directory)

#     print(preprocessed_images)