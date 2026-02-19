import os
import sys
import threading
from pathlib import Path
from typing import Dict
from uuid import UUID

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
project_dir = os.path.dirname(parent_dir)
sys.path.append(project_dir)

from config import Config
from data_layer.ingest.storage.hnsw import HNSWIndex

USER_DATA_DIR = Path(project_dir) / "data" / "users"


class UserFaissManager:
    def __init__(self, dim: int):
        self.dim = dim
        self._indexes: Dict[str, HNSWIndex] = {}
        self._lock = threading.Lock()

    def _index_dir(self, user_id: UUID) -> Path:
        return USER_DATA_DIR / str(user_id)

    def _index_path(self, user_id: UUID) -> Path:
        return self._index_dir(user_id) / "faiss_hnsw.index"

    def get_index(self, user_id: UUID) -> HNSWIndex:
        uid = str(user_id)

        with self._lock:
            if uid in self._indexes:
                return self._indexes[uid]

        idx_path = self._index_path(user_id)
        os.makedirs(idx_path.parent, exist_ok=True)

        index = HNSWIndex(dim=self.dim, index_path=idx_path)

        if idx_path.exists():
            index.load()

        with self._lock:
            self._indexes[uid] = index

        return index
