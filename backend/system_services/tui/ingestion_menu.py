from pathlib import Path

DEFAULT_TEXT_PATH = Path("data/datasets")
DEFAULT_IMAGE_PATH = Path("/home/ajay/Pictures/wallpaper/")
DEFAULT_AUDIO_PATH = Path("data/audio")


def _validate_path(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{label} path does not exist: {resolved}")
    return resolved


def collect_ingestion_config(raw: str = "") -> dict:
    print("\n" + "=" * 60)
    print("SELECT DATA TYPES TO INGEST")
    print("=" * 60)
    print("  1 → Text files   (.txt, .pdf, .doc, .docx)")
    print("  2 → Image files  (.jpg, .jpeg, .png)")
    print("  3 → Audio files  (.mp3, .wav, .m4a, .flac, .ogg)")
    print()
    print("Enter your choices separated by commas  (e.g.  1,2  or  1,2,3)")
    print("Press Enter with no input to default to text only.")

    if raw == "":
        raw = input("\nYour choices: ").strip()

    if not raw:
        choices = {1}
    else:
        try:
            choices = {int(c.strip()) for c in raw.split(",")}
        except ValueError:
            print("Invalid input — defaulting to text only.")
            choices = {1}

    config = {"text": None, "image": None, "audio": None}

    if 1 in choices:
        user_path = (
            input(
                f"\nText file or directory (leave empty for default '{DEFAULT_TEXT_PATH}'): "
            )
            .strip()
            .strip("'\"")
        )
        path = Path(user_path) if user_path else DEFAULT_TEXT_PATH
        config["text"] = _validate_path(path, "Text")
        print(f"  ✓ Text path: {config['text']}")

    if 2 in choices:
        user_path = (
            input(
                f"\nImage file or directory (leave empty for default '{DEFAULT_IMAGE_PATH}'): "
            )
            .strip()
            .strip("'\"")
        )
        path = Path(user_path) if user_path else DEFAULT_IMAGE_PATH
        config["image"] = _validate_path(path, "Image")
        print(f"  ✓ Image path: {config['image']}")

    if 3 in choices:
        user_path = (
            input(
                f"\nAudio file or directory (leave empty for default '{DEFAULT_AUDIO_PATH}'): "
            )
            .strip()
            .strip("'\"")
        )
        path = Path(user_path) if user_path else DEFAULT_AUDIO_PATH
        config["audio"] = _validate_path(path, "Audio")
        print(f"  ✓ Audio path: {config['audio']}")

    if not any(config.values()):
        print("No modalities selected — defaulting to text.")
        config["text"] = _validate_path(DEFAULT_TEXT_PATH, "Text")

    return config
