# NLP Newsletter Crawler

上传的时候理论上每个爬虫来源都指向自己的bucket(oss)

A high-performance web crawler for extracting and processing articles from the NLP Newsletter (https://nlp.elvissaravia.com/).

## Features

- **Concurrent Processing**: Optimized crawler with configurable concurrency settings
- **Resume Support**: Automatically tracks progress and resumes from interruptions
- **Content Extraction**: Converts HTML to clean Markdown format
- **Image Localization**: Downloads and stores all images locally
- **Metadata Preservation**: Captures complete article metadata for future processing
- **Error Handling**: Robust retry mechanisms with exponential backoff

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Playwright browser driver:
```bash
playwright install chromium
```

## Usage

### Basic Crawler
For simple sequential processing:
```bash
python run.py
```

### Optimized Crawler (Recommended)
For high-performance concurrent processing:
```bash
python run_optimized.py
```

Options:
- `--max-concurrent-articles`: Number of articles to process simultaneously (default: 5)
- `--max-concurrent-images`: Number of images to download in parallel (default: 20)
- `--batch-size`: Articles per batch (default: 10)
- `--api-delay`: Delay between API calls in seconds (default: 1.0)
- `--article-delay`: Delay between article processing in seconds (default: 2.0)
- `--no-resume`: Disable resume functionality for fresh start
- `--config`: Custom configuration file path

Example:
```bash
python run_optimized.py --max-concurrent-articles 10 --batch-size 20
```

### Stable Entrypoint (Pinned)
This project pins a stable crawl entry to avoid future regressions:
```bash
python main.py crawl --output crawled_data
```
Notes:
- The crawl flow is protected. Please avoid changing crawler entry/behavior unless necessary.
- Upload flow is protected separately and must not be modified without explicit approval.

## Output Structure

```
crawled_data/
├── articles/         # Markdown files with article content
│   └── {id}_{slug}/
│       └── content.md
├── images/          # Downloaded images
│   ├── covers/      # Article cover images
│   └── content/     # In-article images
└── data/            # JSON metadata files
    ├── articles_metadata.json      # Raw API responses
    ├── processed_articles.json     # Full processed data
    └── recommendation_data.json    # Filtered fields for analysis
```

## Configuration

Create a `config.json` file to customize settings:

```json
{
  "api": {
    "base_url": "https://nlp.elvissaravia.com/api/v1",
    "articles_per_page": 12
  },
  "crawler": {
    "output_dir": "crawled_data",
    "request_delay": 2,
    "timeout": 30,
    "browser": {
      "headless": true,
      "viewport": {
        "width": 1280,
        "height": 720
      }
    }
  }
}
```

## Technical Details

- **Async Architecture**: Built with asyncio for concurrent operations
- **Browser Automation**: Uses Playwright for JavaScript-rendered content
- **Connection Pooling**: Efficient HTTP client with aiohttp
- **Content Processing**: markdownify for HTML to Markdown conversion
- **Progress Tracking**: Automatic checkpointing for resume capability

## Requirements

- Python 3.7+
- See `requirements.txt` for package dependencies

## License

This project is for educational and research purposes. Please respect the original content creators and comply with the NLP Newsletter's terms of service.