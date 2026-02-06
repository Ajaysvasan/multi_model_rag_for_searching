# download_whisper_model.py

import whisper
import os

def download():
    # Where to save the model
    MODEL_DIR = "./models/whisper"
    os.makedirs(MODEL_DIR, exist_ok=True)

    # Which model to download
    # Options: 'tiny' (75MB), 'base' (142MB), 'small' (466MB), 'medium' (1.5GB)
    MODEL_NAME = 'small'  # Recommended

    print(f"Downloading Whisper '{MODEL_NAME}' model...")
    print(f"This is a ONE-TIME download.\n")

    # Download
    model = whisper.load_model(MODEL_NAME, download_root=MODEL_DIR)

    print(f"\n✅ SUCCESS!")
    print(f"Model saved to: {MODEL_DIR}/{MODEL_NAME}.pt")
    print("Your app will now work completely OFFLINE!")