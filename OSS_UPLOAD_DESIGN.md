# OSS 上传设计文档

## 概述

本文档描述了将爬虫系统本地数据上传到 MinIO OSS 存储的完整设计方案。系统将为每个数据源创建独立的存储桶，设置公开访问，并替换文案中的图片地址为公开OSS地址。

## OSS API 分析

基于 `http://localhost:9011/openapi.json` 的分析，系统提供以下核心功能：

### 可用的关键 API 端点

1. **存储桶管理**
   - `POST /api/v1/buckets` - 创建存储桶
   - `PUT /api/v1/buckets/{bucket_name}/make-public` - 设置桶为公开访问
   - `GET /api/v1/buckets` - 列出存储桶

2. **文件管理**
   - `POST /api/v1/objects/{bucket_name}/upload` - 上传文件
   - `GET /api/v1/objects/{bucket_name}/{object_name}/public-url` - 获取公开访问URL

3. **文件信息**
   - `GET /api/v1/objects/{bucket_name}` - 列出桶中对象

## 本地数据结构分析

当前爬虫系统的输出结构：

```
crawled_data/
├── articles/
│   └── {article_slug}/
│       ├── content.md          # Markdown 文件
│       ├── metadata.json       # 文章元数据
│       └── images/
│           ├── cover.jpg       # 封面图片
│           └── img_*.jpg       # 内容图片
└── data/                       # 全局数据文件
    ├── articles_metadata.json
    ├── processed_articles.json
    └── recommendation_data.json
```

### 关键数据字段

从 `metadata.json` 中提取的关键字段：
- `id`, `title`, `subtitle`, `post_date`
- `canonical_url`, `slug`, `description`
- `cover_image`, `local_images`
- `content_markdown` (包含本地图片引用)

## OSS 存储桶组织策略

### 存储桶命名规范

为每个数据源创建独立存储桶：

```
newsletter-articles-{source_id}
```

其中 `source_id` 为数据源标识符（如：`nlp-elvissaravia`）

### 存储桶目录结构

每个存储桶内部组织：

```
newsletter-articles-nlp-elvissaravia/
├── articles/
│   └── {article_slug}/
│       ├── content.md
│       ├── metadata.json
│       └── images/
│           ├── cover.jpg
│           └── img_0.jpg
│           └── img_1.jpg
└── global/
    ├── articles_metadata.json
    ├── processed_articles.json
    └── recommendation_data.json
```

### 公开URL结构

上传后的文件将通过以下URL公开访问：

```
http://localhost:9000/newsletter-articles-{source_id}/articles/{article_slug}/content.md
http://localhost:9000/newsletter-articles-{source_id}/articles/{article_slug}/metadata.json
http://localhost:9000/newsletter-articles-{source_id}/articles/{article_slug}/images/cover.jpg
```

## 上传工作流设计

### 第一阶段：预处理

1. **扫描本地数据**
   - 遍历 `crawled_data/articles/` 目录
   - 收集所有文章目录和文件信息
   - 生成上传任务清单

2. **数据源识别**
   - 从配置或元数据中提取数据源标识
   - 生成对应的存储桶名称

### 第二阶段：存储桶准备

```python
async def prepare_bucket(source_id: str) -> str:
    """准备OSS存储桶"""
    bucket_name = f"newsletter-articles-{source_id}"
    
    # 1. 创建存储桶
    await create_bucket(bucket_name)
    
    # 2. 设置为公开访问
    await make_bucket_public(bucket_name)
    
    return bucket_name
```

### 第三阶段：内容处理与上传

#### 3.1 图片URL替换策略

**原始图片引用**：
```markdown
![](images/img_0.jpg)
![Cover Image](images/cover.jpg)
```

**替换后的公开URL**：
```markdown
![](http://localhost:9000/newsletter-articles-nlp-elvissaravia/articles/article-slug/images/img_0.jpg)
![Cover Image](http://localhost:9000/newsletter-articles-nlp-elvissaravia/articles/article-slug/images/cover.jpg)
```

#### 3.2 上传顺序

```python
async def upload_article(bucket_name: str, article_dir: Path):
    """上传单个文章的完整数据"""
    
    # 1. 上传图片文件
    images_info = await upload_images(bucket_name, article_dir)
    
    # 2. 替换Markdown中的图片链接
    updated_content = replace_image_urls(content_md, images_info)
    
    # 3. 更新metadata中的图片信息
    updated_metadata = update_metadata_urls(metadata, images_info)
    
    # 4. 上传更新后的文件
    await upload_content(bucket_name, updated_content, updated_metadata)
```

### 第四阶段：批量上传

```python
class OSSUploader:
    def __init__(self, base_url: str = "http://localhost:9011"):
        self.base_url = base_url
        self.session = aiohttp.ClientSession()
    
    async def upload_all_data(self, crawled_data_dir: Path, source_id: str):
        """上传所有爬虫数据到OSS"""
        
        # 1. 准备存储桶
        bucket_name = await self.prepare_bucket(source_id)
        
        # 2. 并发上传文章
        article_dirs = list(crawled_data_dir.glob("articles/*"))
        tasks = [
            self.upload_article(bucket_name, article_dir) 
            for article_dir in article_dirs
        ]
        await asyncio.gather(*tasks)
        
        # 3. 上传全局数据文件
        await self.upload_global_data(bucket_name, crawled_data_dir / "data")
```

## URL 替换实现

### 图片URL替换函数

```python
def replace_image_urls_in_markdown(content: str, url_mapping: Dict[str, str]) -> str:
    """替换Markdown中的图片URL"""
    
    # 匹配 ![alt](path) 和 ![](path) 格式
    import re
    
    def replace_func(match):
        alt_text = match.group(1)
        old_path = match.group(2)
        
        # 查找对应的新URL
        if old_path in url_mapping:
            new_url = url_mapping[old_path]
            return f"![{alt_text}]({new_url})"
        return match.group(0)  # 保持原样
    
    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    return re.sub(pattern, replace_func, content)
```

### 元数据URL更新

```python
def update_metadata_image_urls(metadata: Dict, url_mapping: Dict[str, str]) -> Dict:
    """更新metadata中的图片URL"""
    
    # 更新封面图片
    if metadata.get('cover_image'):
        old_path = metadata['cover_image'].get('path')
        if old_path and old_path in url_mapping:
            metadata['cover_image']['public_url'] = url_mapping[old_path]
    
    # 更新内容图片
    if metadata.get('local_images'):
        for img in metadata['local_images']:
            old_path = img.get('path')
            if old_path and old_path in url_mapping:
                img['public_url'] = url_mapping[old_path]
    
    return metadata
```

## 错误处理与重试

### 上传失败处理

```python
class UploadError(Exception):
    pass

async def upload_with_retry(upload_func, max_retries: int = 3):
    """带重试的上传函数"""
    for attempt in range(max_retries):
        try:
            return await upload_func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise UploadError(f"上传失败，已重试{max_retries}次: {str(e)}")
            await asyncio.sleep(2 ** attempt)  # 指数退避
```

### 断点续传支持

```python
class UploadProgress:
    """上传进度追踪"""
    
    def __init__(self, progress_file: Path):
        self.progress_file = progress_file
        self.uploaded_files = set()
        self.failed_files = {}
    
    def mark_uploaded(self, file_path: str):
        self.uploaded_files.add(file_path)
        self.save_progress()
    
    def is_uploaded(self, file_path: str) -> bool:
        return file_path in self.uploaded_files
```

## 配置管理

### OSS上传配置

```json
{
  "oss": {
    "base_url": "http://localhost:9011",
    "source_id": "nlp-elvissaravia",
    "bucket_prefix": "newsletter-articles",
    "max_concurrent_uploads": 10,
    "upload_timeout": 60,
    "retry_attempts": 3,
    "public_base_url": "http://localhost:9000"
  }
}
```

## 实现计划

### Phase 1: 基础上传功能
- [ ] OSS API 客户端封装
- [ ] 存储桶创建和公开设置
- [ ] 基础文件上传功能

### Phase 2: 图片处理
- [ ] 图片URL提取和替换
- [ ] Markdown内容更新
- [ ] 元数据URL更新

### Phase 3: 批量上传
- [ ] 并发上传控制
- [ ] 进度追踪和断点续传
- [ ] 错误处理和重试机制

### Phase 4: 集成测试
- [ ] 端到端测试
- [ ] 性能优化
- [ ] 文档完善

## 使用示例

```bash
# 上传所有爬虫数据到OSS
python upload_to_oss.py --source-id nlp-elvissaravia --data-dir crawled_data

# 仅上传指定文章
python upload_to_oss.py --article-slug "getting-started-with-nlp" --source-id nlp-elvissaravia

# 查看上传进度
python upload_to_oss.py --show-progress
```

## 预期结果

上传完成后，所有文章将通过以下URL公开访问：

- **文章内容**：`http://localhost:9000/newsletter-articles-nlp-elvissaravia/articles/{slug}/content.md`
- **文章元数据**：`http://localhost:9000/newsletter-articles-nlp-elvissaravia/articles/{slug}/metadata.json`
- **文章图片**：`http://localhost:9000/newsletter-articles-nlp-elvissaravia/articles/{slug}/images/{image_name}`

文章Markdown中的所有图片链接将自动替换为对应的公开OSS地址，确保内容可以正常显示。