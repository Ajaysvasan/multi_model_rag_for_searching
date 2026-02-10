"""
Model Download Script - Downloads the GGUF model file.
Run this once before using the RAG system.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import Config


def main():
    print("=" * 50)
    print("GGUF Model Download")
    print("=" * 50)
    print(f"Repo:  {Config.GENERATION_MODEL}")
    print(f"File:  {Config.GENERATION_MODEL_FILE}")
    print(f"Dir:   {Config.MODELS_DIR}")
    print()
    
    Config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = Config.MODELS_DIR / Config.GENERATION_MODEL_FILE
    
    if model_path.exists():
        size_gb = model_path.stat().st_size / (1024**3)
        print(f"Model already exists ({size_gb:.2f} GB)")
        print("Delete it manually if you want to re-download.")
        return 0
    
    print("Downloading model (~4.4GB)...")
    print("This may take several minutes...\n")
    
    try:
        from huggingface_hub import hf_hub_download
        
        downloaded_path = hf_hub_download(
            repo_id=Config.GENERATION_MODEL,
            filename=Config.GENERATION_MODEL_FILE,
            local_dir=str(Config.MODELS_DIR),
        )
        
        size_gb = os.path.getsize(downloaded_path) / (1024**3)
        print(f"\n{'=' * 50}")
        print(f"Download complete!")
        print(f"Path: {downloaded_path}")
        print(f"Size: {size_gb:.2f} GB")
        if size_gb < 5.0:
            print("Under 5GB limit")
        print(f"{'=' * 50}")
        return 0
        
    except Exception as e:
        print(f"\nError: {e}")
        print("\nTroubleshooting:")
        print("1. pip install huggingface_hub")
        print("2. Check disk space (~5GB needed)")
        print("3. Check internet connection")
        return 1


if __name__ == "__main__":
    sys.exit(main())