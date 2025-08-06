# Crawler Architecture Documentation

## Overview

This document describes the technical architecture of the NLP Newsletter Crawler system, a high-performance web scraping solution designed to extract and process newsletter articles.

## System Components

### 1. Core Crawler Module (`src/newsletter_system/crawler/`)

#### Basic Crawler (`newsletter_crawler.py`)
- Sequential processing model
- Single browser instance
- Suitable for small-scale extraction

#### Optimized Crawler (`optimized_crawler.py`)
- **Concurrent Processing**: Uses asyncio with configurable worker pools
- **Browser Page Pool**: Manages multiple Playwright pages for parallel rendering
- **Connection Pooling**: Reuses HTTP connections via aiohttp
- **Semaphore Controls**: Prevents resource exhaustion

### 2. Data Flow Pipeline

```
API Endpoint → Metadata Extraction → Content Processing → Storage
     ↓              ↓                      ↓                ↓
Pagination     JSON Response         HTML→Markdown      File System
```

#### Stage 1: Metadata Collection
- Fetches article listings from API: `https://nlp.elvissaravia.com/api/v1/archive`
- Paginated requests (12 articles per page)
- Extracts: id, title, subtitle, tags, reactions, dates

#### Stage 2: Content Processing
- Navigates to individual article pages
- Waits for JavaScript rendering
- Extracts main content using CSS selectors
- Downloads and localizes images

#### Stage 3: Data Transformation
- HTML to Markdown conversion using markdownify
- Image URL replacement with local paths
- Metadata enrichment and validation

#### Stage 4: Storage
- Structured directory hierarchy
- JSON metadata files for analysis
- Markdown content files
- Localized image assets

## Key Design Patterns

### 1. Async Context Manager Pattern
```python
async with NewsletterCrawler(config) as crawler:
    await crawler.crawl()
```
Ensures proper resource cleanup and browser disposal.

### 2. Producer-Consumer Pattern
- Producer: Article metadata fetcher
- Queue: Article processing queue
- Consumers: Concurrent article processors

### 3. Circuit Breaker Pattern
- Tracks consecutive failures
- Implements exponential backoff
- Prevents cascade failures

## Performance Optimizations

### Concurrency Model
- **Article Processing**: Default 5 concurrent workers
- **Image Downloads**: Default 20 concurrent downloads
- **Batch Processing**: Configurable batch sizes

### Resource Management
- Browser page recycling
- Connection keep-alive
- Memory-conscious streaming

### Error Recovery
- Automatic retry with backoff
- Progress checkpointing
- Resume from interruption

## Configuration System

### Configuration Hierarchy
1. Command-line arguments (highest priority)
2. Configuration file (`config.json`)
3. Default values in code

### Key Parameters
```json
{
  "crawler": {
    "max_concurrent_articles": 5,
    "max_concurrent_images": 20,
    "batch_size": 10,
    "api_delay": 1.0,
    "article_delay": 2.0,
    "request_timeout": 30
  }
}
```

## Error Handling Strategy

### Network Errors
- Retry with exponential backoff
- Maximum 3 retry attempts
- Graceful degradation

### Content Extraction Errors
- Multiple selector fallbacks
- Partial content recovery
- Detailed error logging

### Resource Errors
- Browser crash recovery
- Memory limit protection
- Disk space monitoring

## Monitoring and Logging

### Performance Metrics
- Articles processed per minute
- Average processing time
- Error rates and types

### Progress Tracking
- Real-time progress display
- ETA calculations
- Completion statistics

### Debug Information
- Detailed error traces
- Network request logs
- Browser console output

## Security Considerations

### Rate Limiting
- Configurable delays between requests
- Respects server capacity
- Prevents IP blocking

### Data Privacy
- No personal data collection
- Local storage only
- No external data transmission

## Future Extension Points

### Scalability
- Database integration ready
- Message queue support
- Distributed processing capability

### Content Types
- Video transcript support
- PDF attachment handling
- Interactive content preservation

### Analysis Integration
- Recommendation engine hooks
- Search indexing preparation
- ML pipeline compatibility