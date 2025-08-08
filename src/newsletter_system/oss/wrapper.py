"""Wrapper for OSS uploader to match main.py interface"""

import time
from pathlib import Path
from typing import Dict, Any
from .oss_uploader import NewsletterOSSUploader, MinIOUploader
import re
import asyncio
import json
import logging
from datetime import datetime


class OSSUploaderWrapper:
    """Wrapper class to match the interface expected by main.py"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with config dictionary"""
        self.config = config
        self.endpoint = config.get('base_url', 'http://localhost:9011')
        self.public_base_url = config.get('public_base_url', 'http://localhost:9000')
        self.bucket_name = config.get('bucket_name', 'newsletter-articles-nlp')
        self.uploader = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        pass
        
    async def upload_all(self, base_dir: Path, resume: bool = True) -> Dict[str, Any]:
        """Upload all files from the given directory"""
        start_time = time.time()
        
        try:
            # Create the actual uploader
            self.uploader = NewsletterOSSUploader(
                base_dir=str(base_dir),
                endpoint=self.endpoint
            )
            
            logger = logging.getLogger(__name__)
            
            async with MinIOUploader(self.endpoint, self.public_base_url) as client:
                # Use the bucket name from config
                bucket_name = self.bucket_name
                
                # Clean bucket name (ensure it's valid)
                bucket_name = bucket_name.lower().replace('_', '-').replace(' ', '-')
                bucket_name = re.sub(r'[^a-z0-9-]', '', bucket_name)
                
                # Create bucket and make it public
                logger.info(f"🪣 Setting up bucket: {bucket_name}")
                if not await client.create_bucket(bucket_name):
                    raise Exception("Failed to create bucket")
                    
                if not await client.make_bucket_public(bucket_name):
                    raise Exception("Failed to make bucket public")
                    
                # Get all article directories
                articles_dir = base_dir / "articles"
                if not articles_dir.exists():
                    raise Exception(f"Articles directory not found: {articles_dir}")
                    
                article_dirs = sorted([d for d in articles_dir.iterdir() if d.is_dir()])
                
                logger.info(f"📊 Found {len(article_dirs)} articles to process")
                
                # 建立已上传目录映射：article_id -> 实际目录名，避免依赖 slug/标题推导导致不一致
                article_id_to_dir: Dict[str, str] = {}
                for d in article_dirs:
                    article_id = d.name.split('_')[0]
                    article_id_to_dir[article_id] = d.name

                # Upload articles
                success_count = 0
                failed_count = 0
                sample_urls = []
                
                for article_dir in article_dirs:
                    if await self.uploader.upload_article(client, article_dir, bucket_name):
                        success_count += 1
                        # Collect sample URLs
                        if success_count <= 3:
                            article_id = article_dir.name.split('_')[0]
                            sample_urls.append(f"{self.public_base_url}/{bucket_name}/articles/{article_dir.name}/metadata.json")
                    else:
                        failed_count += 1
                        
                    # Small delay to avoid overwhelming the server
                    await asyncio.sleep(0.1)
                    
                # Upload global metadata files
                logger.info("📋 Uploading global metadata files...")
                
                data_dir = base_dir / "data"
                if data_dir.exists():
                    for json_file in data_dir.glob("*.json"):
                        object_name = f"data/{json_file.name}"
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        # Replace image URLs in global data
                        if json_file.name in ['processed_articles.json', 'articles_metadata.json', 'recommendation_data.json']:
                            # Process each article in the data
                            if isinstance(data, list):
                                for article in data:
                                    if isinstance(article, dict):
                                        article_id = str(article.get('id', ''))
                                        # 优先使用真实存在的目录名
                                        article_dir_name = article_id_to_dir.get(article_id)
                                        if not article_dir_name:
                                            # 回退策略：按爬虫生成规则尝试根据 title 构造安全目录名
                                            title = article.get('title') or article.get('slug', 'article')
                                            safe_title = re.sub(r'[^\w\s-]', '', title).strip()
                                            safe_title = re.sub(r'[-\s]+', '-', safe_title)[:50]
                                            article_dir_name = f"{article_id}_{safe_title}"
                                        
                                        # Replace cover image URL
                                        if 'cover_image' in article and article['cover_image']:
                                            cover = article['cover_image']
                                            if isinstance(cover, str) and cover.startswith('images/'):
                                                article['cover_image'] = f"{self.public_base_url}/{bucket_name}/articles/{article_dir_name}/{cover}"
                                            elif isinstance(cover, dict) and 'url' in cover:
                                                if cover['url'].startswith('images/'):
                                                    cover['url'] = f"{self.public_base_url}/{bucket_name}/articles/{article_dir_name}/{cover['url']}"
                                        
                                        # Replace content images URLs
                                        if 'content_images' in article:
                                            updated_images = []
                                            for img in article['content_images']:
                                                if isinstance(img, str) and img.startswith('images/'):
                                                    updated_images.append(f"{self.public_base_url}/{bucket_name}/articles/{article_dir_name}/{img}")
                                                else:
                                                    updated_images.append(img)
                                            article['content_images'] = updated_images
                                        
                                        # Replace image URLs in content field if exists
                                        if 'content' in article and isinstance(article['content'], str):
                                            # Replace markdown image references
                                            article['content'] = re.sub(
                                                r'!\[([^\]]*)\]\(images/[^)]+\)',
                                                lambda m: f"![{m.group(1)}]({self.public_base_url}/{bucket_name}/articles/{article_dir_name}/{m.group(0).split('(')[1][:-1]})",
                                                article['content']
                                            )
                                            # Replace HTML img src
                                            article['content'] = re.sub(
                                                r'src="images/[^"]+"',
                                                lambda m: f'src="{self.public_base_url}/{bucket_name}/articles/{article_dir_name}/{m.group(0)[5:]}"',
                                                article['content']
                                            )
                            
                        await client.upload_json(bucket_name, object_name, data)
                        logger.info(f"  ✅ Uploaded {object_name}")
                        
                # Save final stats
                self.uploader.progress["stats"] = {
                    "total_articles": len(article_dirs),
                    "uploaded": success_count,
                    "failed": failed_count,
                    "timestamp": datetime.now().isoformat(),
                    "bucket": bucket_name,
                    "endpoint": self.endpoint
                }
                self.uploader.save_progress()
                
                # Print summary
                logger.info("\n" + "="*50)
                logger.info("📊 Upload Summary:")
                logger.info(f"  Total articles: {len(article_dirs)}")
                logger.info(f"  ✅ Successfully uploaded: {success_count}")
                logger.info(f"  ❌ Failed: {failed_count}")
                logger.info(f"  🪣 Bucket: {bucket_name}")
                logger.info(f"  🌐 Endpoint: {self.endpoint}")
                logger.info(f"  📍 Public URL base: {self.public_base_url}/{bucket_name}/")
                logger.info("="*50)
                
                return {
                    'success': True,
                    'uploaded_files': success_count,
                    'elapsed_time_seconds': int(time.time() - start_time),
                    'sample_urls': sample_urls
                }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'uploaded_files': 0,
                'elapsed_time_seconds': int(time.time() - start_time)
            }