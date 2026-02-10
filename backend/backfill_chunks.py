import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import Config

ENCODINGS = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]


def read_file_with_fallback(file_path: str) -> str:
    """Read a file trying multiple encodings."""
    for enc in ENCODINGS:
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    # Last resort: read as bytes and decode with replace
    with open(file_path, "rb") as f:
        return f.read().decode("utf-8", errors="replace")


def main():
    db_path = Config.METADATA_DB_PATH
    print(f"Database: {db_path}")

    conn = sqlite3.connect(str(db_path))

    cur = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE chunk_text IS NULL OR chunk_text = ''"
    )
    empty_count = cur.fetchone()[0]

    cur = conn.execute("SELECT COUNT(*) FROM chunks")
    total_count = cur.fetchone()[0]

    print(f"Total chunks: {total_count}")
    print(f"Empty chunk_text: {empty_count}")

    if empty_count == 0:
        print("All chunks already have text. Nothing to do.")
        conn.close()
        return

    cur = conn.execute("""SELECT chunk_id, source_path, start_offset, end_offset 
           FROM chunks 
           WHERE chunk_text IS NULL OR chunk_text = ''""")
    rows = cur.fetchall()

    file_cache = {}
    fixed = 0
    failed = 0

    for chunk_id, source_path, start_offset, end_offset in rows:
        if source_path not in file_cache:
            if os.path.exists(source_path):
                file_cache[source_path] = read_file_with_fallback(source_path)
            else:
                file_cache[source_path] = None

        content = file_cache[source_path]
        if content is None:
            failed += 1
            continue

        if start_offset < len(content) and end_offset <= len(content):
            chunk_text = content[start_offset:end_offset]
        elif start_offset < len(content):
            chunk_text = content[start_offset:]
        else:
            failed += 1
            continue

        if chunk_text.strip():
            conn.execute(
                "UPDATE chunks SET chunk_text = ? WHERE chunk_id = ?",
                (chunk_text, chunk_id),
            )
            fixed += 1
        else:
            failed += 1

    conn.commit()
    conn.close()

    print(f"\nResults:")
    print(f"  Fixed:  {fixed}")
    print(f"  Failed: {failed}")
    print(f"  Total:  {fixed + failed}")

    if fixed > 0:
        print("\nChunk text has been backfilled successfully!")
    if failed > 0:
        print(
            f"\n{failed} chunks could not be fixed (source files missing or offsets invalid)."
        )
        print("Consider re-ingesting those documents.")


if __name__ == "__main__":
    main()
