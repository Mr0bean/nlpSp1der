#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Newsletter Crawler 主入口程序

统一的爬虫执行入口，提供多种功能：
1. 爬取文章
2. 检查空内容
3. 重新爬取问题文章
4. 上传到OSS
"""

import argparse
import asyncio
import sys
import logging
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.newsletter_system.crawler.newsletter_crawler import CrawlerConfig
from src.newsletter_system.utils.logger import setup_logger
from src.newsletter_system.utils.file_utils import load_json

# 设置日志
logger = setup_logger('main', level=logging.INFO)


def run_crawler(args):
    """运行爬虫"""
    # 直接调用爬虫
    from src.newsletter_system.crawler.newsletter_crawler import NewsletterCrawler, CrawlerConfig
    
    config = CrawlerConfig(
        output_dir=args.output,
        max_concurrent_articles=args.concurrent,
        max_concurrent_images=args.concurrent_images,
        batch_size=args.batch_size,
        api_delay=args.api_delay,
        article_delay=args.article_delay,
        enable_resume=not args.no_resume
    )
    
    async def run():
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
    
    asyncio.run(run())


def upload_to_oss(args):
    """上传到OSS"""
    # 加载配置
    config = load_json('config.json')
    if not config or 'oss' not in config:
        logger.error("OSS configuration not found in config.json")
        return
    
    oss_config = config['oss']
    
    # 覆盖配置中的值（如果命令行提供了）
    if args.bucket:
        oss_config['bucket_name'] = args.bucket
    # 覆盖端点配置（若提供）
    if getattr(args, 'endpoint', None):
        oss_config['base_url'] = args.endpoint
    if getattr(args, 'public_base_url', None):
        oss_config['public_base_url'] = args.public_base_url
    
    # 运行上传
    import asyncio
    from src.newsletter_system.oss import OSSUploader
    
    async def run_upload():
        base_dir = Path(args.source_dir or args.output)
        async with OSSUploader(oss_config) as uploader:
            stats = await uploader.upload_all(base_dir, resume=not args.no_resume)
            return stats
    
    stats = asyncio.run(run_upload())
    
    if stats['success']:
        print(f"\n✅ 上传成功!")
        print(f"  文件数: {stats['uploaded_files']}")
        print(f"  耗时: {stats['elapsed_time_seconds']}秒")
        if stats.get('sample_urls'):
            print(f"\n示例URL:")
            for url in stats['sample_urls'][:3]:
                print(f"  {url}")
    else:
        print(f"\n❌ 上传失败: {stats.get('error', 'Unknown error')}")


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="Newsletter Crawler - 统一执行入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 爬取所有文章
  python main.py crawl
  
  # 上传到OSS
  python main.py upload --bucket my-bucket
  
  # 爬取并上传
  python main.py crawl && python main.py upload
        """
    )
    
    # 添加子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 爬虫命令
    crawl_parser = subparsers.add_parser('crawl', help='运行爬虫')
    crawl_parser.add_argument('--concurrent', type=int, default=5, help='并发文章数')
    crawl_parser.add_argument('--concurrent-images', type=int, default=20, help='并发图片数')
    crawl_parser.add_argument('--batch-size', type=int, default=10, help='批处理大小')
    crawl_parser.add_argument('--api-delay', type=float, default=1.0, help='API延迟(秒)')
    crawl_parser.add_argument('--article-delay', type=float, default=0.5, help='文章延迟(秒)')
    crawl_parser.add_argument('--no-resume', action='store_true', help='不使用断点续传')
    crawl_parser.add_argument('--output', default='crawled_data', help='输出目录')
    
    # 上传命令
    upload_parser = subparsers.add_parser('upload', help='上传到OSS')
    upload_parser.add_argument('--bucket', help='覆盖配置中的bucket名称')
    upload_parser.add_argument('--no-resume', action='store_true', help='不使用断点续传')
    upload_parser.add_argument('--output', default='crawled_data', help='数据目录')
    # 稳定别名与覆盖项，避免后续改动影响
    upload_parser.add_argument('--source-dir', dest='source_dir', default=None, help='数据目录（别名，等价于 --output）')
    upload_parser.add_argument('--endpoint', dest='endpoint', default=None, help='覆盖配置中的endpoint/base_url')
    upload_parser.add_argument('--public-base-url', dest='public_base_url', default=None, help='覆盖配置中的public_base_url')
    
    # 解析参数
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 执行对应命令
    try:
        if args.command == 'crawl':
            run_crawler(args)
        elif args.command == 'upload':
            upload_to_oss(args)
        else:
            parser.print_help()
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\n操作被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()