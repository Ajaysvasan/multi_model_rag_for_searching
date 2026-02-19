import os
import platform
import sys
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

sys.path.append(parent_dir)
from sentence_transformers import SentenceTransformer

from config import Config

try:
    from system_services.tui.ingestion_pipeline import run_ingestion
except:
    raise Exception("whhy the fuck this is not getting imported")


def ingest_command(path_flag=False, source_path: str = ""):
    if not path_flag and source_path == "":
        root_dir = Path.cwd().anchor
        if platform.system().lower() == "linux":
            root_dir = Path(root_dir) / "home"
        source_path = root_dir

    ingestion_config = {
        "text": source_path,
        "image": source_path,
        "audio": source_path,
    }

    try:
        model = SentenceTransformer(Config.EMBED_MODEL_NAME)
        dim = model.get_sentence_embedding_dimension()

        run_ingestion(model=model, dim=dim, ingestion_config=ingestion_config)
        print("Ingestion command finished successfully.")
    except Exception as e:
        print(f"Error during ingestion: {e}")
