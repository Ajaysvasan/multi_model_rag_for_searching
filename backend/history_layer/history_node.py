import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from dataclasses import dataclass
from typing import List

import numpy as np

from cache_layer.TopicState import TopicKey


@dataclass
class HistoryEntry:
    topic_key: TopicKey
    query_embedding: np.ndarray  # shape: (dim,)
    chunk_ids: List[str]
    timestamp: float
