import os
import whisper
import hashlib
from pydub import AudioSegment
from download_whisper import download
from pathlib import Path
from typing import List, Dict


class WhisperAudioToText:
    
    # Supported audio formats
    SUPPORTED_FORMATS = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.opus', '.wma', '.aac'}
    
    def __init__(self, model_name='small', model_dir='./models/whisper'):
        
        self.model_name = model_name
        self.model_dir = model_dir
        
        os.makedirs(self.model_dir, exist_ok=True)
        model_path = os.path.join(self.model_dir, f"{self.model_name}.pt")

        if not os.path.exists(model_path):
            download()  # As whisper is not available on my user we calls download_whisper.py to download it on them
                        # Later we can write it in bat file.

        # Load model (offline)

        self.model = whisper.load_model(
            self.model_name,
            download_root=self.model_dir
        )

    # Processing audio files in the given directory from user given directory

    def find_audio_files(self, directory: str, recursive: bool = True) -> List[str]:
        
        if not os.path.exists(directory):
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        if not os.path.isdir(directory):
            raise NotADirectoryError(f"Path is not a directory: {directory}")
        
        audio_files = []
        directory_path = Path(directory)
        
        if recursive:
            # Search recursively
            for file_path in directory_path.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_FORMATS:
                    # Check whether the given file is a supported audio file.
                    audio_files.append(str(file_path))
        else:
            # Search only in the given directory
            for file_path in directory_path.glob('*'):
                if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_FORMATS:
                    audio_files.append(str(file_path))
        
        return sorted(audio_files)

    # Processing all audio files from the directory
    def process_directory(self, directory: str, language='en', recursive: bool = True) -> List[Dict]:
        
        # Find all audio files
        audio_files = self.find_audio_files(directory, recursive=recursive)
        
        if not audio_files:
            return []
        
        results = []
        
        # Process each audio file
        for idx, audio_path in enumerate(audio_files, 1):
            
            try:
                # Get metadata
                metadata = self.get_audio_metadata(audio_path)
                # print(f"Duration: {metadata['duration_seconds']:.1f}s")
                # print(f" Size: {metadata['file_size_bytes'] / (1024*1024):.2f} MB")
                
                # Convert to text
                transcription = self.convert_to_text(audio_path, language=language)
                
                # Combine results
                result = {
                    'file_path': audio_path,
                    'text': transcription['text'],
                    'metadata': metadata,
                    'language': transcription['language'],
                    'duration': transcription['duration']
                }
                
                results.append(result)
                
            except Exception as e:
                # Still add to results with error info
                results.append({
                    'file_path': audio_path,
                    'text': '',
                    'error': str(e),
                    'metadata': None,
                    'language': None,
                    'duration': 0
                })
                return e
        
        
        return results

    # Speech to text each file from the directory
    def convert_to_text(self, audio_path, language='en'):
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        result = self.model.transcribe(
            audio_path,
            language=language,
            verbose=False,
            fp16=False
        )

        transcript = result['text'].strip()
        detected_language = result.get('language', language or 'unknown')
        segments = result.get('segments', [])
        duration = segments[-1]['end'] if segments else 0

        return {
            'text': transcript,
            'language': detected_language,
            'duration': duration
        }

    # Metadata from the audio file
    def get_audio_metadata(self, audio_path):
        audio = AudioSegment.from_file(audio_path)

        return {
            'filename': os.path.basename(audio_path),
            'file_path': audio_path,
            'file_extension': os.path.splitext(audio_path)[1].lower(),
            'file_size_bytes': os.path.getsize(audio_path)/ (1024 * 1024),
            'duration_seconds': len(audio) / 1000.0,
            'sample_rate': audio.frame_rate,
            'channels': audio.channels,
            'audio_hash': self._hash_file(audio_path)
        }

    def _hash_file(self, filepath):
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()