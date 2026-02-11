import os
import uuid


def run_query_loop(engine, conv_memory, session_id):
    print()
    print("Type your question to get an answer with sources.")
    print(
        "Commands: /retrieve <query> for chunks only, /new for new conversation, quit to exit"
    )
    print()

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "q"]:
                print("\nGoodbye!")
                break

            if user_input.lower() == "/new":
                session_id = str(uuid.uuid4())[:8]
                print(f"\nNew conversation started (session={session_id})\n")
                continue

            if user_input.startswith("/retrieve "):
                query = user_input[10:].strip()
                results = engine.retrieve_with_metadata(query)
                if not results:
                    print("\nNo results found.\n")
                    continue
                print(f"\nFound {len(results)} relevant chunks:\n")
                for i, meta in enumerate(results, 1):
                    print(f"[{i}] {meta['source_path']}")
                    text_preview = meta.get("chunk_text", "")[:150].replace("\n", " ")
                    if text_preview:
                        print(f"    {text_preview}...")
                print()
            else:
                query = user_input
                conv_memory.add_turn(session_id, "user", query)

                response = engine.retrieve_and_generate(query, session_id=session_id)

                print(f"\nAssistant: {response.answer}")

                conv_memory.add_turn(session_id, "assistant", response.answer)

                if response.citations:
                    print("\n" + "-" * 40)
                    print("Sources:")
                    for citation in response.citations:
                        source_name = os.path.basename(citation["source_path"])
                        print(f"  [{citation['id']}] {source_name}")
                print()

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}\n")
