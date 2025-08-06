"""
Configuration management for newsletter system.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

from ..utils.file_utils import load_json, get_project_root


@dataclass
class CrawlerConfig:
    """Configuration for crawler components."""
    base_url: str = "https://nlp.elvissaravia.com"
    api_endpoint: str = "/api/v1/archive"
    api_url: str = "https://nlp.elvissaravia.com/api/v1/archive"
    output_directory: str = "crawled_data"
    request_delay: float = 2.0
    api_delay: float = 1.0
    article_delay: float = 0.2
    timeout: int = 30
    request_timeout: int = 30  # for aiohttp requests
    max_retries: int = 3
    batch_size: int = 10
    max_concurrent_articles: int = 5
    max_concurrent_images: int = 20
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    enable_resume: bool = True
    output_dir: str = "."
    articles_dir: str = "articles"
    images_dir: str = "images"
    data_dir: str = "data"
    browser_timeout: int = 30000  # milliseconds


@dataclass
class SystemConfig:
    """Overall system configuration."""
    crawler: CrawlerConfig
    logging_level: str = "INFO"
    log_file: Optional[str] = None


def load_config(config_path: Optional[str] = None) -> SystemConfig:
    """
    Load configuration from file or use defaults.
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        SystemConfig instance
    """
    if config_path is None:
        # Look for config in multiple locations
        root = get_project_root()
        possible_paths = [
            root / "config.json",
            root / "src" / "newsletter_system" / "config" / "config.json",
            Path("config.json")
        ]
        
        config_data = None
        for path in possible_paths:
            config_data = load_json(str(path))
            if config_data:
                break
    else:
        config_data = load_json(config_path)
    
    if not config_data:
        # Return default configuration
        return SystemConfig(
            crawler=CrawlerConfig()
        )
    
    # Parse configuration
    crawler_data = config_data.get("crawler", {})
    
    return SystemConfig(
        crawler=CrawlerConfig(**crawler_data),
        logging_level=config_data.get("logging_level", "INFO"),
        log_file=config_data.get("log_file")
    )