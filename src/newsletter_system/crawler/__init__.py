"""
爬虫子模块入口。

仅导出基础爬虫 `NewsletterCrawler`，优化版/反爬版在其他入口中提供。
"""

from .newsletter_crawler import NewsletterCrawler
# from .optimized_crawler import OptimizedCrawler  # Commented out due to missing class

__all__ = ['NewsletterCrawler']  # , 'OptimizedCrawler']