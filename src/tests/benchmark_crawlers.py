#!/usr/bin/env python3
"""
爬虫性能对比脚本
"""

import asyncio
import sys
import time
from pathlib import Path
import json

# 添加当前目录到Python路径
sys.path.append(str(Path(__file__).parent))

from crawler.newsletter_crawler import NewsletterCrawler
from crawler.optimized_crawler import OptimizedNewsletterCrawler, CrawlerConfig


async def benchmark_basic_crawler():
    """测试基础爬虫性能"""
    print("🔍 测试基础爬虫...")
    
    start_time = time.time()
    
    try:
        async with NewsletterCrawler(output_dir="test_basic") as crawler:
            # 只获取前5篇文章进行测试
            articles_metadata = await crawler.get_all_articles_metadata()
            test_articles = articles_metadata[:5]
            
            processed_count = 0
            for article in test_articles:
                try:
                    await crawler.process_article(article)
                    processed_count += 1
                except Exception as e:
                    print(f"处理文章失败: {e}")
            
            elapsed = time.time() - start_time
            
            return {
                'name': '基础爬虫',
                'processed_articles': processed_count,
                'total_time': elapsed,
                'avg_time_per_article': elapsed / processed_count if processed_count > 0 else 0
            }
    except Exception as e:
        print(f"基础爬虫测试失败: {e}")
        return None


async def benchmark_optimized_crawler():
    """测试优化爬虫性能"""
    print("🚀 测试优化爬虫...")
    
    start_time = time.time()
    
    try:
        config = CrawlerConfig(
            output_dir="test_optimized",
            max_concurrent_articles=3,
            max_concurrent_images=10,
            batch_size=5,
            enable_resume=False
        )
        
        async with OptimizedNewsletterCrawler(config) as crawler:
            # 只获取前5篇文章进行测试
            articles_metadata = await crawler.get_all_articles_metadata()
            test_articles = articles_metadata[:5]
            
            # 处理文章
            results = await crawler.process_article_batch(test_articles)
            processed_count = len([r for r in results if r is not None])
            
            elapsed = time.time() - start_time
            
            return {
                'name': '优化爬虫',
                'processed_articles': processed_count,
                'total_time': elapsed,
                'avg_time_per_article': elapsed / processed_count if processed_count > 0 else 0
            }
    except Exception as e:
        print(f"优化爬虫测试失败: {e}")
        return None


async def main():
    """主函数"""
    print("📊 爬虫性能对比测试")
    print("=" * 50)
    
    # 测试基础爬虫
    basic_result = await benchmark_basic_crawler()
    
    print("\n" + "=" * 50)
    
    # 测试优化爬虫
    optimized_result = await benchmark_optimized_crawler()
    
    print("\n" + "=" * 50)
    print("📈 性能对比结果:")
    print("=" * 50)
    
    if basic_result:
        print(f"🔍 {basic_result['name']}:")
        print(f"   - 处理文章数: {basic_result['processed_articles']}")
        print(f"   - 总耗时: {basic_result['total_time']:.2f}秒")
        print(f"   - 平均每篇: {basic_result['avg_time_per_article']:.2f}秒")
        print()
    
    if optimized_result:
        print(f"🚀 {optimized_result['name']}:")
        print(f"   - 处理文章数: {optimized_result['processed_articles']}")
        print(f"   - 总耗时: {optimized_result['total_time']:.2f}秒")
        print(f"   - 平均每篇: {optimized_result['avg_time_per_article']:.2f}秒")
        print()
    
    if basic_result and optimized_result:
        if optimized_result['total_time'] > 0:
            speedup = basic_result['total_time'] / optimized_result['total_time']
            print(f"⚡ 性能提升: {speedup:.2f}x")
            
            efficiency_improvement = (basic_result['avg_time_per_article'] - optimized_result['avg_time_per_article']) / basic_result['avg_time_per_article'] * 100
            print(f"📊 效率提升: {efficiency_improvement:.1f}%")
    
    print("\n💡 建议:")
    print("- 对于大规模爬取，推荐使用优化版爬虫")
    print("- 可以通过调整并发参数进一步优化性能")
    print("- 启用断点续传功能可以避免重复工作")


if __name__ == "__main__":
    asyncio.run(main())