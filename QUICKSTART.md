# Quick Start Guide

Get up and running with the NLP Newsletter Crawler in 5 minutes.

## Prerequisites

- Python 3.7 or higher
- pip (Python package manager)
- 2GB free disk space for content storage

## Step 1: Clone the Repository

```bash
git clone <repository-url>
cd 爬虫mlp
```

## Step 2: Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Install browser driver (required for content extraction)
playwright install chromium
```

## Step 3: Run Your First Crawl

### Option A: Quick Test (5 articles)
```bash
python run_optimized.py --batch-size 5
```

### Option B: Full Crawl
```bash
python run_optimized.py
```

## Step 4: Check the Results

Your crawled data will be in the `crawled_data/` directory:

```bash
# View article list
ls crawled_data/articles/

# Read an article
cat crawled_data/articles/*/content.md

# Check metadata
cat crawled_data/data/articles_metadata.json | python -m json.tool | head -50
```

## Common Use Cases

### Resume an Interrupted Crawl
The crawler automatically saves progress. Just run the same command again:
```bash
python run_optimized.py
```

### Fresh Start (Ignore Previous Progress)
```bash
python run_optimized.py --no-resume
```

### Faster Processing (More Concurrent Workers)
```bash
python run_optimized.py --max-concurrent-articles 10 --max-concurrent-images 30
```

### Custom Output Directory
```bash
python run_optimized.py --output-dir my_data
```

## Troubleshooting

### "Playwright not installed" Error
```bash
playwright install chromium
```

### "Module not found" Error
```bash
pip install -r requirements.txt
```

### Slow Performance
- Increase concurrent workers: `--max-concurrent-articles 10`
- Reduce delays: `--api-delay 0.5 --article-delay 1.0`
- Check your internet connection

### Out of Memory
- Reduce batch size: `--batch-size 5`
- Reduce concurrent workers: `--max-concurrent-articles 2`

## Next Steps

1. **Explore the Data**: Check `crawled_data/data/recommendation_data.json` for structured metadata
2. **Customize Settings**: Create a `config.json` file for persistent configuration
3. **Process Content**: Use the Markdown files and metadata for your analysis needs

## Getting Help

- Check `CRAWLER_ARCHITECTURE.md` for technical details
- Review `CLAUDE.md` for AI-assisted development
- See the main `README.md` for comprehensive documentation