#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试爬虫 - 爬取10篇文档
"""

import asyncio
import sys
import time
from pathlib import Path
import json

# 添加 src 到 Python 路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 指向 src 目录

from newsletter_system.crawler.newsletter_crawler import NewsletterCrawler, CrawlerConfig


async def test_crawler_10_articles():
    """测试爬取10篇文档"""
    print("🚀 开始测试爬虫 - 爬取10篇文档")
    print("=" * 50)
    
    # 配置爬虫
    config = CrawlerConfig(
        output_dir="test_crawl_10",
        max_concurrent_articles=3,
        max_concurrent_images=8, 
        batch_size=5,
        enable_resume=True,
        api_delay=0.5,
        article_delay=0.3
    )
    
    start_time = time.time()
    
    try:
        async with NewsletterCrawler(config) as crawler:
            # 获取文章列表
            print("📋 获取文章列表...")
            articles_metadata = await crawler.get_all_articles_metadata()
            
            if not articles_metadata:
                print("❌ 没有获取到文章")
                return
            
            # 只处理前10篇
            test_articles = articles_metadata[:10]
            print(f"📄 准备处理 {len(test_articles)} 篇文章")
            
            # 保存测试用的元数据
            metadata_file = Path(config.output_dir) / "data" / "test_metadata.json"
            metadata_file.parent.mkdir(parents=True, exist_ok=True)
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(test_articles, f, ensure_ascii=False, indent=2)
            
            # 分批处理
            processed_articles = []
            recommendation_data = []
            
            for i in range(0, len(test_articles), config.batch_size):
                batch = test_articles[i:i + config.batch_size]
                batch_num = i // config.batch_size + 1
                total_batches = (len(test_articles) + config.batch_size - 1) // config.batch_size
                
                print(f"\n🔄 处理批次 {batch_num}/{total_batches} ({len(batch)} 篇文章)")
                
                batch_results = await crawler.process_article_batch(batch)
                
                for result in batch_results:
                    if result:
                        processed_articles.append(result['article_data'])
                        recommendation_data.append(result['recommendation_data'])
                        print(f"✅ 完成: {result['article_data'].get('title', 'Unknown')[:50]}...")
                
                print(f"📊 批次完成，已处理 {len(processed_articles)} 篇")
            
            # 保存结果
            data_dir = Path(config.output_dir) / "data"
            
            # 保存处理后的文章
            processed_file = data_dir / "processed_articles.json"
            with open(processed_file, 'w', encoding='utf-8') as f:
                json.dump(processed_articles, f, ensure_ascii=False, indent=2)
            
            # 保存推荐数据
            recommendation_file = data_dir / "recommendation_data.json"
            with open(recommendation_file, 'w', encoding='utf-8') as f:
                json.dump(recommendation_data, f, ensure_ascii=False, indent=2)
            
            elapsed_time = time.time() - start_time
            
            # 统计信息
            total_images = sum(len(article.get('local_images', [])) for article in processed_articles)
            
            print("\n" + "=" * 50)
            print("📊 测试完成统计:")
            print("=" * 50)
            print(f"🎯 目标文章数: 10")
            print(f"✅ 成功处理: {len(processed_articles)}")
            print(f"❌ 失败数量: {len(crawler.progress.failed_articles)}")
            print(f"🖼️  下载图片: {len(crawler.progress.downloaded_images)}")
            print(f"⏱️  总耗时: {elapsed_time:.2f} 秒")
            print(f"⚡ 平均每篇: {elapsed_time/len(processed_articles):.2f} 秒" if processed_articles else "N/A")
            print(f"📁 输出目录: {config.output_dir}")
            
            if crawler.progress.failed_articles:
                print(f"\n❌ 失败文章:")
                for article_id, error in crawler.progress.failed_articles.items():
                    print(f"   - 文章 {article_id}: {error}")
            
            # 展示成功处理的文章
            if processed_articles:
                print(f"\n✅ 成功处理的文章:")
                for i, article in enumerate(processed_articles[:5], 1):
                    title = article.get('title', 'Unknown')[:60]
                    images_count = len(article.get('local_images', []))
                    print(f"   {i}. {title}... ({images_count} 图片)")
                
                if len(processed_articles) > 5:
                    print(f"   ... 还有 {len(processed_articles) - 5} 篇")
            
            return {
                'processed': len(processed_articles),
                'failed': len(crawler.progress.failed_articles),
                'images': len(crawler.progress.downloaded_images),
                'time': elapsed_time
            }
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """主函数"""
    result = await test_crawler_10_articles()
    
    if result:
        print(f"\n🎉 测试成功完成!")
        print(f"性能指标: {result['processed']}/10 篇文章，{result['time']:.1f}秒")
    else:
        print(f"\n💥 测试失败")


if __name__ == "__main__":
    asyncio.run(main())