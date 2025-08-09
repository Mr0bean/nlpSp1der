#!/usr/bin/env python3
"""
爬虫性能对比脚本
"""

import asyncio
import sys
import time
from pathlib import Path
import json

# 添加 src 到 Python 路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 指向 src 目录

from newsletter_system.crawler.newsletter_crawler import NewsletterCrawler, CrawlerConfig


async def benchmark_basic_crawler():
    """测试基础爬虫性能"""
    print("🔍 测试基础爬虫...")
    
    start_time = time.time()
    
    try:
        config = CrawlerConfig(
            output_dir="test_basic",
            max_concurrent_articles=3,
            max_concurrent_images=8,
            batch_size=5,
            enable_resume=False
        )
        async with NewsletterCrawler(config) as crawler:
            # 只获取前5篇文章进行测试
            articles_metadata = await crawler.get_all_articles_metadata()
            test_articles = articles_metadata[:5]

            # 一次批量处理
            results = await crawler.process_article_batch(test_articles)
            processed_count = len([r for r in results if r is not None])

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
    """占位：优化爬虫（当前未实现），返回 None。"""
    print("🚀 测试优化爬虫（占位，未实现）...")
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
    print("- 若遇限流/验证码，建议使用 run_anti_detect.py（反爬增强版）")
    print("- 可以通过调整并发与延迟参数进一步优化性能")
    print("- 启用断点续传功能可以避免重复工作")


if __name__ == "__main__":
    asyncio.run(main())