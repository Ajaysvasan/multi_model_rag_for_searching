# TUI_services — API reference

[← Back to BACKEND.md](../BACKEND.md) · [Design notes](TUI_services.md)

## Command line

```bash
cd backend
python agent.py start                    # interactive Q&A
python agent.py ingest                   # broad scan (see the warning below)
python agent.py ingest --path ~/Documents/papers
python agent.py blame                    # last recorded timings
python agent.py clear                    # delete local index + databases
```

> `ingest` with no `--path` starts at `/home` on Linux and walks recursively.
> Always pass `--path`.

## `start`

```python
from TUI_services.start import start
start()      # blocks; Ctrl-C or "q"/"quit"/"exit " to leave
```

Initialises the system, times it, then loops: read a question, preprocess,
retrieve and generate, print the answer, list the source files with a text
preview.

> Raises `NameError` when a citation resolves to a non-text source (image or
> audio) — `extracted_text` is only bound inside the text-extension branch.

## `ingest_command`

```python
from TUI_services.ingest_command import ingest_command

ingest_command(path_flag=False, source_path="/home/me/papers")   # specific path
ingest_command()                                                  # broad scan
```

| Parameter | Default | Meaning |
|---|---|---|
| `path_flag` | `False` | With `source_path` empty, triggers the filesystem-root scan |
| `source_path` | `""` | Directory or file to ingest |

The path is used for all three modalities at once:

```python
{"text": source_path, "image": source_path, "audio": source_path}
```

Errors are caught and printed rather than raised, so a failure does not abort a
long run.

## `blame`

```python
from TUI_services.blame import blame_command
blame_command()      # prints logs/tui_perf.json
```

```json
{"timestamp": "2026-04-03T17:17:53Z", "last_query": {"total": 168.1987}}
```

Only the most recent record exists (see `write_logs` below).

## `logger`

```python
import time
from TUI_services.logger import write_logs

t0 = time.time()
do_work()
write_logs("init", t0, time.time())        # or "last_query", or any label
```

Writes `logs/tui_perf.json`, creating the directory if needed.

> Opens the file with `"w"`, so each call **replaces** the previous record. For
> a cumulative trace, change the mode to `"a"` — the format is already one JSON
> object per line.

## `clear`

```python
from TUI_services.clear import clear_data
clear_data()
```

Deletes, when present:

- `Config.INDEX_PATH` and `Config.INDEX_PATH + ".ids"`
- `Config.METADATA_DB_PATH`
- `Config.CACHE_HISTORY_DB_PATH`
- `Config.DB_PATH` (when different from the above)
- `Config.METADATA_PATH`

Prints each deletion and a final count. Destructive and unconfirmed — every
ingested document must be re-indexed afterwards. It does not touch PostgreSQL,
downloaded models, or per-user server indexes under `data/users/`.

## Adding a command

```python
# TUI_services/summarise.py
def summarise_command(path: str) -> None:
    ...
```

```python
# agent.py
sub = subparser.add_parser("summarise", help="Summarise a document")
sub.add_argument("--path", type=str, required=True)

match args.command:
    case "summarise":
        summarise_command(args.path)
```
