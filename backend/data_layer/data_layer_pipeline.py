# This is a data pipeline layer
# Which takes the data or files from the given director , extract the chunks , embed them and then store the embeddings in the
# Vector DB(HNSW) along with the metadata
import os
import sys

# including all the packages so that ImportError can be avoided
data_layer_dir = os.path.dirname(os.path.abspath(__file__))
storage_path = os.path.join(data_layer_dir, "ingest/storage")
sys.path.append(storage_path)

from ingest.chunker import TextChunker
from ingest.normalizer import TextNormalizer
from ingest.storage.embedding import EmbeddingBatcher
from ingest.storage.hnsw import HNSWIndex
from ingest.Text_files_processing.file_loader import FileLoader
from ingest.Text_files_processing.text_extractor import TextExtractor
