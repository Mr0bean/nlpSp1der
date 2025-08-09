"""
Newsletter 爬虫系统核心包。

本包聚合了爬虫、工具、配置等子模块，建议通过显式导入使用：
    from newsletter_system.crawler import NewsletterCrawler
"""

from .crawler import NewsletterCrawler  # , OptimizedCrawler

__all__ = ['NewsletterCrawler']  # , 'OptimizedCrawler']