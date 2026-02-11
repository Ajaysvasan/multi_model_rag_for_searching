import traceback

from query_loop import run_query_loop
from system_init import initialize_system


def _ask_mode():
    """Top-level menu: ingest new data or chat."""
    print()
    print("=" * 60)
    print("WHAT WOULD YOU LIKE TO DO?")
    print("=" * 60)
    print("  1 → Ingest new data  (add files/folders to the knowledge base)")
    print("  2 → Chat             (query the existing knowledge base)")
    print()
    choice = input("Your choice [1/2]: ").strip()
    return "ingest" if choice == "1" else "chat"


def main():
    try:
        mode = _ask_mode()

        if mode == "ingest":
            from ingestion_menu import collect_ingestion_config

            ingestion_config = collect_ingestion_config()
            engine, metadata_store, conv_memory, session_id = initialize_system(
                ingestion_config=ingestion_config
            )
        else:
            # Chat — only ingest if no index exists (handled inside initialize_system)
            engine, metadata_store, conv_memory, session_id = initialize_system()

        run_query_loop(engine, conv_memory, session_id)
        metadata_store.close()
        conv_memory.close()
    except KeyboardInterrupt:
        print("\n\nInterrupted.")
    except Exception as e:
        print(f"\nFatal error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
