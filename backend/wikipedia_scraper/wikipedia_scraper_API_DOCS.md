# wikipedia_scraper — API reference

[← Back to BACKEND.md](../BACKEND.md) · [Design notes](wikipedia_scraper.md)

> Requires `beautifulsoup4`, which is not in `requirements.txt`:
> `pip install beautifulsoup4`

## Running it

```bash
cd backend
python wikipedia_scraper/main.py
```

Logs to `logs/wikipedia_scraper.log` and writes the corpus to the configured
output directory. Run it as a script: it inserts its own directory on
`sys.path`, so importing it from application code shadows the project's root
`config.py`.

## Configuration

Edit `wikipedia_scraper/config.py`:

| Setting | Meaning |
|---|---|
| `USER_AGENT` | Sent to the MediaWiki API. Identify yourself; Wikipedia asks for a contact |
| `MAX_PAGES_PER_TOPIC` | Cap per topic — the main size control |
| `MAX_DEPTH` | Link hops from a seed. Raising it blurs topic labels |
| `OUTPUT_DIR` | Corpus destination |

## Stage APIs

### `WikipediaSeeds`

```python
from seeds import WikipediaSeeds

seeds = WikipediaSeeds()
topics = seeds.get_topics()                 # {"oncology": ["Cancer", "Breast cancer"], ...}
```

### `WikipediaCrawler`

```python
from crawler import WikipediaCrawler

crawler = WikipediaCrawler(config)
pages = crawler.crawl_topic("oncology", ["Cancer", "Breast cancer"])
# [{"title": ..., "pageid": ..., "content": ..., "depth": ...}, ...]
```

Breadth-first, stopping at `MAX_PAGES_PER_TOPIC` or `MAX_DEPTH`. `crawler.visited`
persists across topics so a shared page is not fetched twice.

### `ContentExtractor` / `TextCleaner`

```python
from extractor import ContentExtractor
from cleaner import TextCleaner

prose = ContentExtractor().extract(raw_page)   # drops infoboxes, navboxes, references
text  = TextCleaner().clean(prose)             # whitespace, citation markers
```

### `TopicAssigner` / `DataExporter`

```python
from topic_assigner import TopicAssigner
from exporter import DataExporter

labelled = TopicAssigner().assign(pages, topic_id="oncology")
DataExporter(config).export(labelled)
```

## End-to-end

```python
import sys, logging
from pathlib import Path
sys.path.insert(0, str(Path("wikipedia_scraper").resolve()))

from config import Config          # the SCRAPER's config, not the project's
from seeds import WikipediaSeeds
from crawler import WikipediaCrawler
from extractor import ContentExtractor
from cleaner import TextCleaner
from topic_assigner import TopicAssigner
from exporter import DataExporter

logging.basicConfig(level=logging.INFO)
cfg = Config()

crawler, extractor = WikipediaCrawler(cfg), ContentExtractor()
cleaner, assigner, exporter = TextCleaner(), TopicAssigner(), DataExporter(cfg)

for topic_id, seed_pages in WikipediaSeeds().get_topics().items():
    pages = crawler.crawl_topic(topic_id, seed_pages)
    cleaned = [
        {**p, "content": cleaner.clean(extractor.extract(p))}
        for p in pages
    ]
    exporter.export(assigner.assign(cleaned, topic_id))
```

## Feeding the corpus into the pipeline

```bash
python agent.py ingest --path data/datasets/wikipedia
```

Or via the API, once authenticated:

```python
requests.post("http://localhost:8000/upload", json={
    "filePaths": ["/abs/path/data/datasets/wikipedia"],
    "type": "document",
    "access_token": access_token,
})
```

## Etiquette

Set a real `USER_AGENT` with contact details, keep `MAX_PAGES_PER_TOPIC`
modest, and cache output rather than re-crawling — the crawler has no persistent
cache, so every run re-fetches. Wikipedia content is CC BY-SA; redistributing a
derived corpus carries attribution obligations.
