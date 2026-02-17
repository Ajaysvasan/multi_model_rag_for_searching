"""Main module which will be integrated with the frontend"""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import platform
import threading

from config import Config
from fastapi import FastAPI
from pydantic import BaseModel
from system_init import initialize_system


class Query(BaseModel):
    query: str


if platform.system().lower() not in Config.OS:
    raise OSError(
        f"The operating system {platform.system()} is not supported. Supporated Os list : {Config.OS}"
    )

if platform.system().lower() != "windows":
    engine, metadata_store, conv_memory, session_id, query_preprocessor = (
        initialize_system()
    )
    model_thread = None  # responsible for loading the model in the memory
else:
    # for windows
    pass

app = FastAPI(title="AI assistant API")


@app.post("query")
def query_endpoint(query: Query):

    intent_query = query_preprocessor.preprocess_query(query.query)
    response = engine.retrieve_and_generate(query, intent_query)
    conv_memory.add_turn(session_id, "assistant", response.answer)
    sources = []
    if response.citations:
        for citation in response.citations:
            source = citation["source_path"]
            sources.append(source)
    print(sources)

    return {
        "response": response.answer,
        "sources": sources,
    }


if __name__ == "__main__":
    # testing if the function is working or not
    pass
