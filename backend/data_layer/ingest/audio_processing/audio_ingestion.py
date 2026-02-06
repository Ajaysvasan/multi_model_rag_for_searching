from audio_to_text import WhisperAudioToText
    
def ingest_audio(audio_directory: str):

    # We must download "ffmpeg" ---> winget install ffmpeg ---> For windows
    # This is must be written in bat file.

    # Initialize converter (uses cached model - offline)
    converter = WhisperAudioToText(
        # This model must be downloaded...
        model_name='small',
        model_dir='./models/whisper'
    )

    # Remove quotes if user wrapped the path in quotes
    audio_directory = audio_directory.strip('"').strip("'")

    if audio_directory:
        # Process all audio files in the directory
        results = converter.process_directory(
            directory=audio_directory,
            language='en',  # or None for auto-detect
            recursive=True  # Set to False to skip subdirectories
        )
        
        for idx, result in enumerate(results, 1):
            
            if 'error' in result:
                print(f" Error: {result['error']}")
            else:
                record = {idx : results}

    return record

# Both the line will be called from frontend or main backend for processing the audio directory and audio files

# audio_directory = input("\nEnter the directory path containing audio files: ").strip()
# ingest = ingest_audio(audio_directory)
# print(ingest)