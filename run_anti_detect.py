#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用反爬虫检测增强版爬虫的命令行入口。

功能特性：
- 通过 `EnhancedCrawlerConfig` 配置更保守的并发与更长的延迟；
- 可选代理支持；
- 控制台输出关键统计，指导限流情况下的参数调优。

使用示例：
    # 基础用法（推荐）
    python run_anti_detect.py

    # 仅处理前 5 篇（快速联调）
    python run_anti_detect.py --limit 5

    # 极低速策略（最安全）
    python run_anti_detect.py --concurrent 1 --batch 2 --article-delay 10
"""

import asyncio
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.newsletter_system.crawler.anti_detect_crawler import AntiDetectCrawler, EnhancedCrawlerConfig
from src.newsletter_system.utils.logger import setup_logger

# 设置日志
logger = setup_logger('anti_detect_crawler', level=logging.INFO)


async def main(args):
    """主函数"""
    # 创建配置
    config = EnhancedCrawlerConfig(
        output_dir=args.output,
        max_concurrent_articles=args.concurrent,  # 降低并发数
        batch_size=args.batch,  # 减小批次大小
        api_delay=args.api_delay,
        article_delay=args.article_delay,
        enable_resume=not args.no_resume,
        use_proxy=args.use_proxy,
        proxy_url=args.proxy_url,
        smart_delay=True,
        min_delay=3.0,
        max_delay=10.0,
        batch_delay=20.0,
        rate_limit_delay=60.0
    )
    
    print("\n" + "="*60)
    print("🛡️  反爬虫增强版 Newsletter 爬虫")
    print("="*60)
    print(f"📁 输出目录: {config.output_dir}")
    print(f"🔧 并发数: {config.max_concurrent_articles} 篇文章")
    print(f"📦 批次大小: {config.batch_size}")
    print(f"⏱️  API延迟: {config.api_delay}秒")
    print(f"⏱️  文章延迟: {config.article_delay}秒")
    print(f"🔄 最大重试: {config.max_retries}次")
    print(f"💾 断点续传: {'启用' if config.enable_resume else '禁用'}")
    if config.use_proxy:
        print(f"🌐 代理: {config.proxy_url}")
    print("="*60 + "\n")
    
    try:
        async with AntiDetectCrawler(config) as crawler:
            # 获取文章列表
            print("📋 获取文章列表...")
            articles = await crawler.get_all_articles_metadata()
            
            if not articles:
                print("❌ 未获取到文章")
                return
            
            print(f"✅ 获取到 {len(articles)} 篇文章")
            
            # 如果指定了限制，只处理部分文章
            if args.limit:
                articles = articles[:args.limit]
                print(f"🎯 限制处理前 {args.limit} 篇文章")
            
            # 处理文章
            print("\n🚀 开始处理文章（使用反爬策略）...")
            print("💡 提示：处理速度会比较慢，这是为了避免被检测")
            
            stats = await crawler.process_articles(articles)
            
            # 输出统计
            print("\n" + "="*60)
            print("📊 处理完成统计：")
            print(f"  总文章数: {stats.get('total_articles', 0)}")
            print(f"  ✅ 成功处理: {stats.get('processed_articles', 0)}")
            print(f"  ❌ 处理失败: {stats.get('failed_articles', 0)}")
            print(f"  ⏭️  跳过（已处理）: {stats.get('skipped_articles', 0)}")
            print(f"  📁 输出目录: {config.output_dir}")
            print("="*60)
            
            # 如果有失败的，给出建议
            if stats.get('failed_articles', 0) > 0:
                print("\n💡 建议：")
                print("  1. 增加延迟时间：--article-delay 10")
                print("  2. 减少并发数：--concurrent 1")
                print("  3. 使用代理：--use-proxy --proxy-url http://proxy:port")
                print("  4. 稍后再试（网站可能暂时限流）")
            
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断操作")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        logger.error(f"爬虫错误: {e}", exc_info=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="反爬虫增强版 Newsletter 爬虫",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 基础使用（推荐）
  python run_anti_detect.py
  
  # 限制处理数量（测试用）
  python run_anti_detect.py --limit 5
  
  # 极低速爬取（最安全）
  python run_anti_detect.py --concurrent 1 --batch 2 --article-delay 10
  
  # 使用代理
  python run_anti_detect.py --use-proxy --proxy-url http://127.0.0.1:7890
  
  # 禁用断点续传（重新开始）
  python run_anti_detect.py --no-resume
        """
    )
    
    parser.add_argument('--output', default='crawled_data', help='输出目录')
    parser.add_argument('--concurrent', type=int, default=2, help='并发文章数（默认2）')
    parser.add_argument('--batch', type=int, default=3, help='批次大小（默认3）')
    parser.add_argument('--limit', type=int, help='限制处理文章数（测试用）')
    parser.add_argument('--api-delay', type=float, default=2.0, help='API请求延迟（秒）')
    parser.add_argument('--article-delay', type=float, default=5.0, help='文章处理延迟（秒）')
    # 注意：最大重试次数由内部策略控制，因此此参数暂不生效
    # parser.add_argument('--max-retries', type=int, default=5, help='最大重试次数')
    parser.add_argument('--no-resume', action='store_true', help='禁用断点续传')
    parser.add_argument('--use-proxy', action='store_true', help='使用代理')
    parser.add_argument('--proxy-url', help='代理地址（如 http://127.0.0.1:7890）')
    
    args = parser.parse_args()
    
    # 运行爬虫
    asyncio.run(main(args))