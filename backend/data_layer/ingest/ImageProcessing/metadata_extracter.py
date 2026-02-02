import os
import hashlib
import datetime
from PIL import Image, ExifTags
import numpy as np
import cv2


class MetadataExtractor:
    def extract_metadata(
        self,
        image_path: str,
        image: Image.Image,
        *,
        has_text: bool = None,
        image_type: str = None,
        caption: str = None,
        source_doc: str = None,
        page_number: int = None
    ):
        
        metadata = {} # Storing in dictionary for easy access of image data

        stat = os.stat(image_path)

        metadata["Image source path"] = image_path
        metadata["filename"] = os.path.basename(image_path)
        metadata["file_extension"] = os.path.splitext(image_path)[1].lower()
        metadata["file_size_bytes"] = stat.st_size
        metadata["created_time"] = self._to_iso(stat.st_ctime)
        metadata["modified_time"] = self._to_iso(stat.st_mtime)

        # Extracting Image properties from the image 

        width, height = image.size
        metadata["width"] = width
        metadata["height"] = height
        metadata["aspect_ratio"] = round(width / height, 3)
        metadata["color_mode"] = image.mode

        
        metadata["exif"] = self._extract_exif(image)

        # Image type and captioning

        metadata["has_text"] = has_text
        metadata["image_type"] = image_type
        metadata["caption"] = caption

        metadata["source_document"] = source_doc
        metadata["page_number"] = page_number

        metadata["image_hash"] = self._compute_image_hash(image)
        metadata["edge_density"] = self._compute_edge_density(image)

        return metadata


    def _to_iso(self, timestamp):
        return datetime.datetime.fromtimestamp(timestamp).isoformat()

    def _extract_exif(self, image: Image.Image):
        exif_data = {}
        try:
            exif = image.getexif()
            if not exif:
                return exif_data

            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                exif_data[tag] = value
        except Exception:
            pass

        return exif_data

    def _compute_image_hash(self, image: Image.Image):
        
        img_bytes = image.tobytes()
        return hashlib.sha256(img_bytes).hexdigest()

    def _compute_edge_density(self, image: Image.Image):
        
        gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        return float(np.sum(edges > 0) / edges.size)

