#!/usr/bin/env python3

import os
import json
import asyncio
import aiohttp
import aiofiles
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import re
import logging
from urllib.parse import quote

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MinIOUploader:
    def __init__(self, endpoint: str = "http://localhost:9011", access_key: str = "", secret_key: str = ""):
        self.endpoint = endpoint.rstrip('/')
        self.api_base = f"{self.endpoint}/api/v1"
        self.access_key = access_key
        self.secret_key = secret_key
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def create_bucket(self, bucket_name: str) -> bool:
        """创建存储桶"""
        try:
            async with self.session.post(
                f"{self.api_base}/buckets",
                json={"bucket_name": bucket_name}
            ) as resp:
                if resp.status == 201:
                    logger.info(f"✅ Created bucket: {bucket_name}")
                    return True
                elif resp.status == 400:
                    # Bucket might already exist
                    logger.info(f"ℹ️  Bucket already exists: {bucket_name}")
                    return True
                else:
                    error = await resp.text()
                    logger.error(f"Failed to create bucket {bucket_name}: {error}")
                    return False
        except Exception as e:
            logger.error(f"Error creating bucket {bucket_name}: {e}")
            return False
            
    async def make_bucket_public(self, bucket_name: str) -> bool:
        """设置桶为公开访问"""
        try:
            async with self.session.put(
                f"{self.api_base}/buckets/{bucket_name}/make-public"
            ) as resp:
                if resp.status == 200:
                    logger.info(f"✅ Made bucket public: {bucket_name}")
                    return True
                else:
                    error = await resp.text()
                    logger.error(f"Failed to make bucket public {bucket_name}: {error}")
                    return False
        except Exception as e:
            logger.error(f"Error making bucket public {bucket_name}: {e}")
            return False
            
    async def upload_file(self, bucket_name: str, object_name: str, file_path: str, metadata: Optional[Dict] = None) -> Optional[str]:
        """上传文件到MinIO并返回公开URL"""
        try:
            # Read file
            async with aiofiles.open(file_path, 'rb') as f:
                file_data = await f.read()
                
            # Prepare form data
            data = aiohttp.FormData()
            data.add_field('file', file_data, filename=os.path.basename(file_path))
            
            # Build URL with query parameters
            url = f"{self.api_base}/objects/{bucket_name}/upload"
            params = {'object_name': object_name}
            if metadata:
                params['metadata'] = json.dumps(metadata)
                
            async with self.session.post(url, data=data, params=params) as resp:
                if resp.status == 201:
                    result = await resp.json()
                    # Construct public URL
                    public_url = f"{self.endpoint}/{bucket_name}/{object_name}"
                    logger.debug(f"✅ Uploaded: {object_name} -> {public_url}")
                    return public_url
                else:
                    error = await resp.text()
                    logger.error(f"Failed to upload {object_name}: {error}")
                    return None
        except Exception as e:
            logger.error(f"Error uploading {file_path}: {e}")
            return None
            
    async def upload_json(self, bucket_name: str, object_name: str, data: Dict) -> Optional[str]:
        """上传JSON数据到MinIO"""
        try:
            # Convert to JSON bytes
            json_data = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
            
            # Prepare form data
            form_data = aiohttp.FormData()
            form_data.add_field('file', json_data, filename=os.path.basename(object_name))
            
            # Build URL with query parameters
            url = f"{self.api_base}/objects/{bucket_name}/upload"
            params = {'object_name': object_name}
                
            async with self.session.post(url, data=form_data, params=params) as resp:
                if resp.status == 201:
                    result = await resp.json()
                    # Construct public URL
                    public_url = f"{self.endpoint}/{bucket_name}/{object_name}"
                    logger.debug(f"✅ Uploaded JSON: {object_name} -> {public_url}")
                    return public_url
                else:
                    error = await resp.text()
                    logger.error(f"Failed to upload JSON {object_name}: {error}")
                    return None
        except Exception as e:
            logger.error(f"Error uploading JSON {object_name}: {e}")
            return None

class NewsletterOSSUploader:
    def __init__(self, base_dir: str = "crawled_data", endpoint: str = "http://localhost:9011"):
        self.base_dir = Path(base_dir)
        self.endpoint = endpoint
        self.progress_file = self.base_dir / "oss_upload_progress.json"
        self.progress = self.load_progress()
        
    def load_progress(self) -> Dict:
        """加载上传进度"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {"uploaded_articles": [], "stats": {}}
        
    def save_progress(self):
        """保存上传进度"""
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)
            
    def get_bucket_name(self, source: str = "nlp-newsletter") -> str:
        """根据数据源获取bucket名称"""
        # 清理名称，确保符合bucket命名规则
        bucket_name = source.lower().replace('_', '-').replace(' ', '-')
        bucket_name = re.sub(r'[^a-z0-9-]', '', bucket_name)
        return bucket_name
        
    def replace_image_urls(self, content: str, image_mappings: Dict[str, str]) -> str:
        """替换内容中的本地图片路径为OSS URL"""
        for local_path, oss_url in image_mappings.items():
            # 处理各种可能的路径格式
            patterns = [
                local_path,
                f"../{local_path}",
                f"../../{local_path}",
                local_path.replace('crawled_data/', ''),
                local_path.replace('images/', ''),
            ]
            
            for pattern in patterns:
                content = content.replace(pattern, oss_url)
                
        return content
        
    async def upload_article(self, client: MinIOUploader, article_dir: Path, bucket_name: str) -> bool:
        """上传单个文章及其所有资源"""
        article_id = article_dir.name
        
        # Skip if already uploaded
        if article_id in self.progress.get("uploaded_articles", []):
            logger.info(f"⏭️  Skipping already uploaded: {article_id}")
            return True
            
        logger.info(f"📤 Uploading article: {article_id}")
        
        try:
            # Load metadata
            metadata_file = article_dir / "metadata.json"
            if not metadata_file.exists():
                logger.warning(f"No metadata found for {article_id}")
                return False
                
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                
            # Load content
            content_file = article_dir / "content.md"
            if not content_file.exists():
                logger.warning(f"No content found for {article_id}")
                return False
                
            with open(content_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Upload images and collect mappings
            image_mappings = {}
            
            # Check if there's an images directory in the article folder
            article_images_dir = article_dir / "images"
            
            # Upload all images in the article's images directory
            if article_images_dir.exists() and article_images_dir.is_dir():
                for img_file in article_images_dir.iterdir():
                    if img_file.is_file() and img_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                        oss_path = f"articles/{article_id}/images/{img_file.name}"
                        oss_url = await client.upload_file(bucket_name, oss_path, str(img_file))
                        if oss_url:
                            # Map both possible paths
                            image_mappings[f"images/{img_file.name}"] = oss_url
                            image_mappings[img_file.name] = oss_url
                            logger.debug(f"  📷 Uploaded image: {img_file.name}")
            
            # Upload cover image if exists
            if 'cover_image' in metadata and metadata['cover_image']:
                local_cover = metadata['cover_image']
                # Handle dict format cover images
                if isinstance(local_cover, dict):
                    local_cover = local_cover.get('url', '') or local_cover.get('path', '')
                    
                if local_cover and isinstance(local_cover, str):
                    # Try to find the cover image
                    if local_cover.startswith('images/'):
                        # Check in article images dir first
                        cover_filename = local_cover.replace('images/', '')
                        article_cover_path = article_images_dir / cover_filename
                        global_cover_path = self.base_dir / local_cover
                        
                        if article_cover_path.exists():
                            # Already uploaded above, just update metadata
                            if local_cover in image_mappings:
                                metadata['cover_image'] = image_mappings[local_cover]
                        elif global_cover_path.exists():
                            # Upload from global images directory
                            oss_path = f"articles/{article_id}/images/{global_cover_path.name}"
                            oss_url = await client.upload_file(bucket_name, oss_path, str(global_cover_path))
                            if oss_url:
                                image_mappings[local_cover] = oss_url
                                metadata['cover_image'] = oss_url
                            
            # Upload content images (already handled above if in article dir)
            content_images = metadata.get('content_images', [])
            for img_path in content_images:
                if img_path.startswith('images/') and img_path not in image_mappings:
                    # Only upload if not already uploaded from article dir
                    local_path = self.base_dir / img_path
                    if local_path.exists():
                        oss_path = f"articles/{article_id}/images/{local_path.name}"
                        oss_url = await client.upload_file(bucket_name, oss_path, str(local_path))
                        if oss_url:
                            image_mappings[img_path] = oss_url
                            
            # Update content images in metadata
            if image_mappings:
                metadata['content_images'] = [
                    image_mappings.get(img, img) for img in content_images
                ]
                
            # Replace image URLs in content
            if image_mappings:
                content = self.replace_image_urls(content, image_mappings)
                
            # Upload updated content
            content_path = f"articles/{article_id}/content.md"
            content_bytes = content.encode('utf-8')
            
            form_data = aiohttp.FormData()
            form_data.add_field('file', content_bytes, filename='content.md')
            
            url = f"{client.api_base}/objects/{bucket_name}/upload"
            params = {'object_name': content_path}
            
            async with client.session.post(url, data=form_data, params=params) as resp:
                if resp.status != 201:
                    error = await resp.text()
                    logger.error(f"Failed to upload content: {error}")
                    return False
                    
            # Upload metadata
            metadata_path = f"articles/{article_id}/metadata.json"
            metadata_url = await client.upload_json(bucket_name, metadata_path, metadata)
            if not metadata_url:
                return False
                
            # Mark as uploaded
            self.progress["uploaded_articles"].append(article_id)
            self.save_progress()
            
            logger.info(f"✅ Successfully uploaded: {article_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading article {article_id}: {e}")
            return False
            
    async def upload_all(self):
        """上传所有文章到OSS"""
        async with MinIOUploader(self.endpoint) as client:
            # Get data source (for now we use a single source)
            bucket_name = self.get_bucket_name("nlp-newsletter")
            
            # Create bucket and make it public
            logger.info(f"🪣 Setting up bucket: {bucket_name}")
            if not await client.create_bucket(bucket_name):
                logger.error("Failed to create bucket")
                return
                
            if not await client.make_bucket_public(bucket_name):
                logger.error("Failed to make bucket public")
                return
                
            # Get all article directories
            articles_dir = self.base_dir / "articles"
            if not articles_dir.exists():
                logger.error(f"Articles directory not found: {articles_dir}")
                return
                
            article_dirs = sorted([d for d in articles_dir.iterdir() if d.is_dir()])
            
            logger.info(f"📊 Found {len(article_dirs)} articles to process")
            
            # Upload articles
            success_count = 0
            failed_count = 0
            
            for article_dir in article_dirs:
                if await self.upload_article(client, article_dir, bucket_name):
                    success_count += 1
                else:
                    failed_count += 1
                    
                # Small delay to avoid overwhelming the server
                await asyncio.sleep(0.1)
                
            # Upload global metadata files
            logger.info("📋 Uploading global metadata files...")
            
            data_dir = self.base_dir / "data"
            if data_dir.exists():
                for json_file in data_dir.glob("*.json"):
                    object_name = f"data/{json_file.name}"
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Replace image URLs in global data
                    if json_file.name in ['processed_articles.json', 'articles_metadata.json']:
                        data_str = json.dumps(data)
                        for article_id in self.progress.get("uploaded_articles", []):
                            # Simple pattern replacement for image paths
                            data_str = re.sub(
                                r'"images/[^"]+\.(?:jpg|jpeg|png|gif|webp)"',
                                lambda m: f'"{self.endpoint}/{bucket_name}/articles/{article_id}/{m.group(0)[1:]}"',
                                data_str
                            )
                        data = json.loads(data_str)
                        
                    await client.upload_json(bucket_name, object_name, data)
                    
            # Save final stats
            self.progress["stats"] = {
                "total_articles": len(article_dirs),
                "uploaded": success_count,
                "failed": failed_count,
                "timestamp": datetime.now().isoformat(),
                "bucket": bucket_name,
                "endpoint": self.endpoint
            }
            self.save_progress()
            
            # Print summary
            logger.info("\n" + "="*50)
            logger.info("📊 Upload Summary:")
            logger.info(f"  Total articles: {len(article_dirs)}")
            logger.info(f"  ✅ Successfully uploaded: {success_count}")
            logger.info(f"  ❌ Failed: {failed_count}")
            logger.info(f"  🪣 Bucket: {bucket_name}")
            logger.info(f"  🌐 Endpoint: {self.endpoint}")
            logger.info(f"  📍 Public URL base: {self.endpoint}/{bucket_name}/")
            logger.info("="*50)

async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Upload newsletter data to MinIO OSS")
    parser.add_argument("--base-dir", default="crawled_data", help="Base directory containing articles")
    parser.add_argument("--endpoint", default="http://localhost:9011", help="MinIO endpoint URL")
    parser.add_argument("--reset", action="store_true", help="Reset upload progress and start fresh")
    
    args = parser.parse_args()
    
    uploader = NewsletterOSSUploader(args.base_dir, args.endpoint)
    
    if args.reset:
        uploader.progress = {"uploaded_articles": [], "stats": {}}
        uploader.save_progress()
        logger.info("🔄 Reset upload progress")
    
    await uploader.upload_all()

if __name__ == "__main__":
    asyncio.run(main())