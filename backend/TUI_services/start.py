import os
import sys
import time

from system_services.tui.system_init import initialize_system

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from .logger import write_logs


def start():
    start_time = time.time()
    engine, metadata_store, conv_memory, session_id, query_preprocessor = (
        initialize_system()
    )
    end_time = time.time()
    write_logs("init", start_time, end_time)
    try:
        while True:
            query = input(">")
            if query.lower() in ["q", "quit", "exit "]:
                print("Good bye")
                break
            conv_memory.add_turn(session_id, "user", query)
            intent_query = query_preprocessor.preprocess_query(query)
            start_time = time.time()
            result = engine.retrieve_and_generate(
                query, intent_query, session_id=session_id
            )
            end_time = time.time()
            write_logs("last_query", start_time, end_time)
            conv_memory.add_turn(session_id, "assistant", result.answer)
            print(f"Assistant: {result.answer}")
            sources = set()
            if result.citations:
                print("Sources")
                for citation in result.citations:
                    source = citation["source_path"]
                    sources.add(source)

            print(f"The sources are")
            for source in sources:
                print(f"{source}\n")
    except KeyboardInterrupt:
        print("Bye!")
