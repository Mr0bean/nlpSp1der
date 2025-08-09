#!/usr/bin/env python3
"""
Newsletter 爬虫运行脚本（基础版）。

用途：
- 面向常规站点/轻度风控场景，直接基于 `NewsletterCrawler` 进行抓取。
- 通过命令行参数配置输出目录、并发、批次与延迟等关键行为。

提示：
- 若频繁出现限流或验证码，建议改用 `run_anti_detect.py`。
"""

import asyncio
import sys
import argparse
from pathlib import Path

# 添加当前目录到Python路径
sys.path.append(str(Path(__file__).parent.parent))

from newsletter_system.crawler.newsletter_crawler import NewsletterCrawler, CrawlerConfig

async def run_crawler(config: CrawlerConfig):
    """运行爬虫"""
    print("🚀 开始爬取Newsletter文章...")
    print(f"🔧 配置: 并发{config.max_concurrent_articles}篇文章, {config.max_concurrent_images}张图片")
    
    async with NewsletterCrawler(config) as crawler:
        stats = await crawler.crawl_all()
        
        print("\n✅ 爬取完成!")
        print(f"📊 统计信息:")
        print(f"   - 总文章数: {stats.get('total_articles', 0)}")
        print(f"   - 处理成功: {stats.get('processed_articles', 0)}")
        print(f"   - 下载图片: {stats.get('total_images', 0)}")
        print(f"   - 输出目录: {stats.get('output_directory', '')}")
        
        return stats

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Newsletter爬虫系统")
    parser.add_argument("--output-dir", "-o", default="crawled_data", help="输出目录")
    parser.add_argument("--max-concurrent-articles", type=int, default=5, help="最大并发文章处理数")
    parser.add_argument("--max-concurrent-images", type=int, default=20, help="最大并发图片下载数")
    parser.add_argument("--batch-size", type=int, default=10, help="批处理大小")
    parser.add_argument("--no-resume", action="store_true", help="禁用断点续传")
    parser.add_argument("--api-delay", type=float, default=1.0, help="API请求间隔（秒）")
    parser.add_argument("--article-delay", type=float, default=0.5, help="文章处理间隔（秒）")
    
    args = parser.parse_args()
    
    # 创建配置
    config = CrawlerConfig(
        output_dir=args.output_dir,
        max_concurrent_articles=args.max_concurrent_articles,
        max_concurrent_images=args.max_concurrent_images,
        batch_size=args.batch_size,
        enable_resume=not args.no_resume,
        api_delay=args.api_delay,
        article_delay=args.article_delay
    )
    
    # 运行爬虫
    await run_crawler(config)
    
    print("\n🎉 爬虫任务完成!")

if __name__ == "__main__":
    asyncio.run(main())