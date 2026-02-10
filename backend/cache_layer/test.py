from cache import TopicCacheManager
from TopicState import TopicKey


def make_key(name: str) -> TopicKey:
    return TopicKey(
        topic_label=name,
        modality_filter="text",
        retrieval_policy="default",
    )


def print_levels(step: str, cache: TopicCacheManager):
    dump = cache.debug_dump_levels()
    print(f"\n=== {step} ===")
    print("L1:", [k.topic_label for k in dump["L1"]])
    print("L2:", [k.topic_label for k in dump["L2"]])
    print("L3:", [k.topic_label for k in dump["L3"]])
    print("Counts:", cache.debug_counts())


def main():
    cache = TopicCacheManager()

    sequence = [
        "A",
        "B",
        "C",  # Fill L3
        "A",  # A should promote to L2 (2 hits)
        "A",
        "A",  # A should promote to L1 (4 hits)
        "B",
        "B",  # B should promote to L2
        "D",  # Insert D -> L3 (may evict oldest if full)
        "E",  # Insert E -> L3 (force eviction)
        "B",
        "B",  # B should promote to L1, may demote A if L1 full
        "C",  # Access C again (if still present)
    ]

    for i, name in enumerate(sequence, 1):
        key = make_key(name)

        state = cache.lookup(key)
        if state is None:
            # Cache miss path
            state = cache.insert_new(key, cached_chunk_ids=[f"{name}_chunk"])

        print_levels(f"Step {i}: access {name}", cache)


if __name__ == "__main__":
    main()
