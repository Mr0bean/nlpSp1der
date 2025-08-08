# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**⚠️ IMPORTANT: This project contains ONLY crawler functionality. Recommendation engine features exist only in documentation and research - no implementation code is included.**

## Commands

### Setup and Installation
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browser driver (required for web scraping)
playwright install chromium
```

### Running the Application

**Basic Version:**
```bash
# Run complete flow (crawler + recommendation)
python run.py

# Run crawler only
python run.py --crawl-only

# Run recommendation engine only
python run.py --recommend-only

# Specify custom output directory
python run.py --output-dir my_data
```

**Optimized Version (Recommended):**
```bash
# Run optimized crawler with default settings
python run_optimized.py

# Run with custom concurrency settings
python run_optimized.py --max-concurrent-articles 10 --max-concurrent-images 30

# Run with configuration file
python run_optimized.py --config config.json

# Run with resume disabled (fresh start)
python run_optimized.py --no-resume

# Fine-tune performance
python run_optimized.py --batch-size 20 --api-delay 0.5 --article-delay 0.2
```

### Development Commands
Since there are no specific test files or linting configurations, you can run:
```bash
# Check Python syntax
python -m py_compile src/newsletter_system/crawler/newsletter_crawler.py

# Run with debugging
python -u run.py  # Unbuffered output for real-time logging
```

## Protected Flows

These flows are pinned and must not be modified without explicit approval:

- Upload flow: `main.py upload` and code under `src/newsletter_system/oss/*`, plus `config.json` `oss.*` contract.
- Crawl stable entry: `python main.py crawl --output <dir>` should remain supported as a stable interface.

## Architecture Overview

This is a Newsletter crawling system focused on content extraction and processing:

### 1. Newsletter Crawler
**Basic Version** (`crawler/newsletter_crawler.py`):
- Sequential processing with basic error handling
- Single browser instance for all articles
- Basic retry mechanism

**Optimized Version** (`crawler/optimized_crawler.py`) - **Recommended**:
- **Concurrent Processing**: Configurable concurrent article processing (default: 5)
- **Batch Image Downloads**: Parallel image downloads with semaphore control (default: 20 concurrent)
- **Resume Support**: Automatic progress tracking and resume from interruption
- **Advanced Error Handling**: Exponential backoff retry mechanism with detailed logging
- **Resource Management**: Browser page pool and connection pooling
- **Performance Monitoring**: Detailed timing and throughput statistics

**Key Features**:
- Uses Playwright for browser automation and JavaScript rendering
- Async/await pattern with aiohttp for concurrent downloads
- Converts HTML to Markdown using markdownify
- Downloads and localizes all images
- Preserves complete metadata for future processing

**Output Structure**:
- `articles/`: Markdown files with article content
- `images/`: Downloaded images (cover + content images)
- `data/`: JSON files with metadata and processing results

### 2. Entry Points
- **Basic Crawler** (`src/scripts/run.py`): Simple sequential processing
- **Optimized Crawler** (`src/scripts/run_optimized.py`): Concurrent processing with advanced features
- **Legacy Scripts** (`run.py`, `run_optimized.py`): Redirect to new structure for compatibility

## Key Design Patterns

1. **Async Context Manager**: NewsletterCrawler uses `async with` for resource management
2. **Configuration-driven**: All settings in `config.json`
3. **Graceful Degradation**: Optional dependencies with fallback warnings
4. **Structured Data Pipeline**: Raw API → Processed → Recommendation-ready

## Data Flow Architecture

### 1. Crawler → Recommendation Engine Data Flow
The system follows a clear ETL pattern:

**Extract Phase** (`NewsletterCrawler.get_all_articles_metadata()`):
- Paginated API calls to `https://nlp.elvissaravia.com/api/v1/archive`
- Handles pagination with offset/limit (12 articles per batch)
- Rate limiting: 1-second delay between API requests, 2-second delay between article processing

**Transform Phase** (`NewsletterCrawler.process_article()`):
- Downloads and localizes images (cover + content images)
- Converts HTML to Markdown using markdownify
- Extracts recommendation-specific fields: `['id', 'title', 'subtitle', 'post_date', 'audience', 'type', 'reactions', 'wordcount', 'postTags', 'cover_image', 'description', 'canonical_url', 'slug']`

**Load Phase**:
- Saves to three separate JSON files in `data/` directory:
  - `articles_metadata.json`: Raw API responses
  - `processed_articles.json`: Full processed data with content
  - `recommendation_data.json`: Filtered fields for recommendation engine

### 2. Recommendation Engine Data Structures

**Key Data Structures Used**:
```python
# Article recommendation data structure
{
    "id": int,                    # Unique article identifier
    "title": str,                 # Primary content for similarity matching
    "subtitle": str,              # Secondary content (2x weight in TF-IDF)
    "description": str,           # Tertiary content
    "postTags": [                 # Structured tag data
        {"name": str, "slug": str, "id": str}
    ],
    "reactions": {"❤": int},      # Engagement metrics
    "wordcount": int,             # Content length
    "post_date": "ISO timestamp", # Temporal features
    "type": "newsletter|tutorial|paper", # Content categorization
    "audience": "everyone|only_paid"      # Access level
}
```

## Advanced Implementation Details

### 1. Error Handling and Retry Mechanisms

**Crawler Error Handling**:
- Network failures: Graceful degradation with detailed logging
- Missing content selectors: Falls back through multiple CSS selectors: `['article', '.post-content', '.entry-content', '.article-content', '[data-testid="post-content"]', '.markup']`
- Image download failures: Continues processing without failing entire article
- Playwright timeouts: 10-second wait for article selector, networkidle state for full page load

**Configuration-Based Retry Settings** (`config.json`):
```json
{
  "crawler": {
    "request_delay": 2,      # Delay between article processing
    "max_retries": 3,        # Not yet implemented in current codebase
    "timeout": 30            # Request timeout
  }
}
```

### 2. Recommendation Algorithm Implementation

**Multi-Strategy Approach**:
1. **Content-Based Filtering**: Uses scikit-learn TF-IDF with parameters:
   - `max_features=5000`: Vocabulary size limit
   - `ngram_range=(1,2)`: Unigrams and bigrams
   - `min_df=1, max_df=0.8`: Document frequency filtering
   - `stop_words='english'`: English stopword removal

2. **Popularity Scoring Algorithm**:
```python
def calculate_popularity_score(article):
    score = 0.0
    score += sum(article.reactions.values()) * 0.3  # Engagement weight
    
    # Word count sweet spot optimization
    if 300 <= article.wordcount <= 2000: score += 10
    elif article.wordcount > 2000: score += 5
    
    # Temporal decay function
    days_old = (now - article.post_date).days
    if days_old <= 7: score += 20      # Recent boost
    elif days_old <= 30: score += 10   # Month boost  
    elif days_old <= 90: score += 5    # Quarter boost
    
    # Content type weighting
    if article.type == 'newsletter': score += 5
    
    return score
```

3. **Fallback Mechanism**: When scikit-learn unavailable, uses simple keyword overlap matching

### 3. MVP Integration Context

This crawler is designed as the **data ingestion layer** for a larger MVP system documented in `/MVP/01-MVP技术架构设计.md`:

**Target MVP Architecture**:
- **Database**: PostgreSQL with JSONB fields for flexible metadata
- **Search**: Elasticsearch with dense vector embeddings (384-dim)
- **Storage**: Minio for image/file assets
- **API**: FastAPI with user behavior tracking

**Integration Points**:
- Crawler output JSON directly maps to MVP database schema
- `recommendation_data.json` structure aligns with Elasticsearch article index
- Local image storage pattern matches Minio bucket structure (`images/covers/`, `images/content/`)

### 4. Performance and Scalability Considerations

**Current Bottlenecks**:
- Single-threaded Playwright browser instance (one article at a time)
- No connection pooling for HTTP requests
- Images downloaded sequentially, not in parallel
- No database persistence (JSON file-based storage)

**Scalability Patterns from MVP Design**:
- Task queue system using database table (`task_queue` in MVP schema)
- User behavior tracking for recommendation improvement
- Elasticsearch for search and similarity queries at scale
- Container-based deployment with health checks

## Important Notes

- The crawler respects rate limiting (2-second delay by default)
- All dependencies are optional with import guards - the code won't crash if packages are missing
- The system is designed to be resumable - processed data is saved incrementally
- Image processing includes optimization and format conversion
- Chinese characters in the directory name (爬虫mlp) may require UTF-8 terminal support
- **Playwright Browser Management**: Properly managed with async context managers - browser instances are automatically cleaned up
- **Memory Management**: Large datasets are processed incrementally and saved to disk to prevent memory issues