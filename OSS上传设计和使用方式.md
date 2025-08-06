# Newsletter OSS 上传系统设计和使用方式

本文档详细说明 Newsletter 爬虫系统的对象存储 (OSS/MinIO) 上传功能的设计架构和使用方法。

## 系统架构

### 核心组件

```
OSS上传系统
├── OSSUploader (主上传器)
├── OSSWrapper (接口适配器) 
├── MinIO客户端 (底层存储)
└── 进度管理 (断点续传)
```

### 技术栈
- **存储后端**: MinIO (S3兼容对象存储)
- **Python SDK**: minio-py
- **并发控制**: asyncio + ThreadPoolExecutor
- **进度持久化**: JSON文件
- **错误重试**: 指数退避算法

## 数据存储结构

### 存储路径设计

```
bucket-name/
└── articles/                    # 文章根目录
    └── {source_id}/            # 数据源标识 (nlp-elvissaravia)
        └── {article_id}/       # 文章ID目录
            ├── content.md      # Markdown内容
            ├── metadata.json   # 文章元数据
            └── images/         # 图片目录
                ├── cover.jpg   # 封面图片 (如果有)
                └── img_*.jpg   # 内容图片
```

### 路径示例

```
test-newsletter-upload/
└── articles/
    └── nlp-elvissaravia/
        ├── 169787925/
        │   ├── content.md
        │   ├── metadata.json
        │   └── images/
        │       ├── img_0.jpg
        │       ├── img_1.jpg
        │       └── img_2.jpg
        ├── 169783090/
        │   ├── content.md
        │   ├── metadata.json
        │   └── images/
        │       └── cover.jpg
        └── ...
```

## 配置设置

### config.json 配置

```json
{
  "oss": {
    "base_url": "http://localhost:9011",           // MinIO服务地址
    "public_base_url": "http://60.205.160.74:9000", // 公网访问地址
    "bucket_name": "newsletter-articles-nlp",      // 默认存储桶名称
    "source_id": "nlp-elvissaravia",               // 数据源标识
    "max_concurrent_uploads": 10,                  // 最大并发上传数
    "upload_timeout": 60,                          // 上传超时时间(秒)
    "retry_attempts": 3,                           // 重试次数
    "chunk_size": 8192                             // 文件块大小
  }
}
```

### 环境变量

```bash
# MinIO认证信息 (必需)
export MINIO_ACCESS_KEY="your-access-key"
export MINIO_SECRET_KEY="your-secret-key"

# 可选: 覆盖配置文件中的endpoint
export MINIO_ENDPOINT="http://localhost:9000"
```

## 使用方式

### 1. 基本上传命令

```bash
# 使用默认配置上传所有文章
python3 main.py upload

# 指定自定义bucket名称
python3 main.py upload --bucket my-custom-bucket

# 不使用断点续传，重新上传所有文件
python3 main.py upload --no-resume
```

### 2. 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--bucket` | 指定bucket名称 | `newsletter-articles-nlp` |
| `--no-resume` | 禁用断点续传 | 启用 |
| `--source-dir` | 指定源目录 | `crawled_data` |

### 3. Python 代码调用

```python
import asyncio
from src.newsletter_system.oss.oss_uploader import OSSUploader

async def upload_articles():
    # 创建上传器实例
    uploader = OSSUploader(
        endpoint='http://localhost:9000',
        access_key='your-access-key',
        secret_key='your-secret-key',
        bucket_name='my-bucket',
        source_id='nlp-elvissaravia'
    )
    
    # 上传指定目录的所有文章
    await uploader.upload_all_articles('crawled_data')

# 运行上传
asyncio.run(upload_articles())
```

### 4. 单文章上传

```python
async def upload_single_article():
    uploader = OSSUploader(...)
    
    # 上传单篇文章
    article_path = "crawled_data/articles/169787925_Top-AI-Papers-of-the-Week"
    success = await uploader.upload_article(article_path)
    
    if success:
        print("上传成功")
    else:
        print("上传失败")
```

## 核心功能特性

### 1. 自动Bucket管理

```python
# 自动创建bucket
await uploader.ensure_bucket_exists()

# 自动设置公共读权限
await uploader.set_bucket_policy_public()
```

**功能说明：**
- 检查bucket是否存在，不存在则自动创建
- 自动设置bucket为公共读取权限
- 支持跨区域bucket创建

### 2. 智能文件发现

```python
# 自动扫描文章目录
articles = uploader.discover_articles("crawled_data/articles")

# 每篇文章包含：
# - content.md (必需)
# - metadata.json (必需)  
# - images/ 目录下的所有图片 (可选)
```

**发现规则：**
- 扫描 `crawled_data/articles/` 下的所有子目录
- 每个子目录代表一篇文章
- 必须包含 `content.md` 和 `metadata.json`
- 自动包含 `images/` 目录下的所有文件

### 3. 断点续传机制

```python
# 进度文件位置
progress_file = "crawled_data/upload_progress.json"

# 进度数据结构
{
  "uploaded_articles": ["169787925", "169783090"],
  "failed_articles": {
    "169333505": "Connection timeout"
  },
  "upload_start_time": "2024-08-07T01:28:52",
  "last_update_time": "2024-08-07T01:30:52"
}
```

**工作原理：**
- 上传前检查进度文件，跳过已上传的文章
- 实时更新进度，支持中断后继续
- 记录失败原因，便于问题排查
- 使用 `--no-resume` 可忽略进度重新上传

### 4. 并发上传控制

```python
# 使用信号量控制并发数
semaphore = asyncio.Semaphore(max_concurrent_uploads)

async def upload_with_semaphore(article_path):
    async with semaphore:
        return await self.upload_single_article(article_path)

# 批量并发上传
tasks = [upload_with_semaphore(path) for path in article_paths]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

**性能优化：**
- 默认10个并发上传任务
- 自动负载均衡，避免服务器过载
- 支持动态调整并发数

### 5. 错误处理和重试

```python
# 指数退避重试机制
async def upload_with_retry(self, file_path, object_name):
    for attempt in range(self.retry_attempts):
        try:
            await self.upload_file(file_path, object_name)
            return True
        except Exception as e:
            if attempt < self.retry_attempts - 1:
                delay = 2 ** attempt  # 1s, 2s, 4s
                await asyncio.sleep(delay)
                continue
            else:
                logger.error(f"Final upload failed: {e}")
                return False
```

**错误类型处理：**
- **网络错误**: 自动重试，最多3次
- **认证错误**: 立即失败，检查密钥
- **权限错误**: 立即失败，检查bucket权限  
- **空间不足**: 立即失败，检查存储配额

## 监控和日志

### 1. 上传进度监控

```bash
# 实时查看上传日志
tail -f upload.log

# 输出示例:
# 2024-08-07 01:28:53 - INFO - 🪣 Setting up bucket: test-newsletter-upload
# 2024-08-07 01:28:53 - INFO - ✅ Created bucket: test-newsletter-upload
# 2024-08-07 01:28:53 - INFO - 📊 Found 180 articles to process
# 2024-08-07 01:28:55 - INFO - ✅ Successfully uploaded: 100722694_Top-ML-Papers-of-the-Week
```

### 2. 进度统计脚本

```python
# 检查上传进度
def check_upload_progress():
    with open('crawled_data/upload_progress.json') as f:
        progress = json.load(f)
    
    total_articles = len(os.listdir('crawled_data/articles'))
    uploaded = len(progress['uploaded_articles'])
    failed = len(progress['failed_articles'])
    
    print(f"上传进度: {uploaded}/{total_articles}")
    print(f"成功率: {uploaded/(uploaded+failed)*100:.1f}%")
    print(f"失败数: {failed}")
```

### 3. 存储空间检查

```bash
# 检查bucket大小 (需要mc工具)
mc du minio/test-newsletter-upload

# 检查文件数量
mc ls --recursive minio/test-newsletter-upload | wc -l

# 检查上传完整性
python3 -c "
import json
with open('crawled_data/upload_progress.json') as f:
    progress = json.load(f)
print(f'已上传: {len(progress[\"uploaded_articles\"])} 篇文章')
print(f'失败: {len(progress[\"failed_articles\"])} 篇文章')
"
```

## 性能优化

### 1. 并发参数调优

```json
{
  "oss": {
    "max_concurrent_uploads": 20,    // 高性能服务器
    "upload_timeout": 120,          // 大文件超时
    "chunk_size": 16384            // 网络优化
  }
}
```

**调优建议：**
- **高带宽网络**: `max_concurrent_uploads: 20-50`
- **低带宽网络**: `max_concurrent_uploads: 5-10`  
- **大文件上传**: 增加 `upload_timeout`
- **小文件优化**: 减小 `chunk_size`

### 2. 网络优化

```python
# 启用连接复用
client = Minio(
    endpoint,
    access_key=access_key,
    secret_key=secret_key,
    secure=secure,
    http_client=urllib3.PoolManager(
        maxsize=50,        # 连接池大小
        timeout=60,        # 连接超时
        retries=3          # 重试次数
    )
)
```

### 3. 内存优化

```python
# 分批上传，避免内存溢出
batch_size = 50
for i in range(0, len(articles), batch_size):
    batch = articles[i:i+batch_size]
    await upload_batch(batch)
    
    # 批次间暂停，释放资源
    await asyncio.sleep(1)
```

## 故障排查

### 1. 常见错误及解决方案

| 错误类型 | 症状 | 解决方案 |
|---------|------|----------|
| 认证失败 | `AccessDenied` | 检查 `MINIO_ACCESS_KEY/SECRET_KEY` |
| 网络超时 | `Connection timeout` | 增加 `upload_timeout`，检查网络 |
| Bucket不存在 | `NoSuchBucket` | 自动创建或手动创建bucket |
| 权限不足 | `AccessDenied on PUT` | 检查用户权限，设置bucket policy |
| 文件不存在 | `FileNotFound` | 检查源文件路径，重新爬取 |

### 2. 调试模式

```bash
# 启用详细日志
export MINIO_DEBUG=1
python3 main.py upload --bucket debug-test

# 测试单篇文章上传
python3 -c "
import asyncio
from src.newsletter_system.oss.oss_uploader import OSSUploader
uploader = OSSUploader(...)
asyncio.run(uploader.upload_article('crawled_data/articles/169787925_Top-AI-Papers-of-the-Week'))
"
```

### 3. 数据完整性检查

```python
# 检查上传完整性
async def verify_upload_integrity():
    uploader = OSSUploader(...)
    
    # 获取本地文章列表
    local_articles = uploader.discover_articles("crawled_data/articles")
    
    # 检查远程文件
    for article_id in local_articles:
        # 检查content.md
        exists = await uploader.object_exists(f"articles/nlp-elvissaravia/{article_id}/content.md")
        if not exists:
            print(f"Missing: {article_id}/content.md")
        
        # 检查metadata.json
        exists = await uploader.object_exists(f"articles/nlp-elvissaravia/{article_id}/metadata.json")
        if not exists:
            print(f"Missing: {article_id}/metadata.json")
```

## 最佳实践

### 1. 生产环境部署

```bash
# 1. 设置环境变量
export MINIO_ACCESS_KEY="production-key"
export MINIO_SECRET_KEY="production-secret"
export MINIO_ENDPOINT="https://oss.yourcompany.com"

# 2. 使用专用bucket
python3 main.py upload --bucket newsletter-production

# 3. 监控上传状态
python3 main.py upload --bucket newsletter-production 2>&1 | tee upload.log

# 4. 定期备份进度文件
cp crawled_data/upload_progress.json backups/upload_progress_$(date +%Y%m%d).json
```

### 2. 数据迁移

```bash
# 从一个bucket迁移到另一个bucket
python3 -c "
import asyncio
from src.newsletter_system.oss.oss_uploader import OSSUploader

async def migrate():
    # 从源bucket下载
    source = OSSUploader(bucket_name='old-bucket')
    # 上传到目标bucket  
    target = OSSUploader(bucket_name='new-bucket')
    
    # 实现迁移逻辑
    await migrate_between_buckets(source, target)

asyncio.run(migrate())
"
```

### 3. 自动化脚本

```bash
#!/bin/bash
# auto_upload.sh - 自动爬取和上传脚本

set -e

echo "开始爬取..."
python3 main.py crawl

echo "开始上传..."
python3 main.py upload --bucket newsletter-$(date +%Y%m)

echo "清理临时文件..."
rm -f crawled_data/upload_progress.json

echo "完成!"
```

## 安全考虑

### 1. 访问控制

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": "*",
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::newsletter-public/*"]
    },
    {
      "Effect": "Deny", 
      "Principal": "*",
      "Action": ["s3:PutObject", "s3:DeleteObject"],
      "Resource": ["arn:aws:s3:::newsletter-public/*"]
    }
  ]
}
```

### 2. 数据加密

```python
# 启用服务端加密
client.put_object(
    bucket_name,
    object_name,
    data,
    length,
    metadata={
        'x-amz-server-side-encryption': 'AES256'
    }
)
```

### 3. 访问日志

```python
# 记录所有上传操作
import logging

upload_logger = logging.getLogger('oss_upload')
upload_logger.info(f"Upload: {object_name} by {user_id}")
```

## 重要修复说明

### 图片URL公开访问地址修复

**问题描述：**
之前版本中，上传到OSS后的图片URL使用的是后端API地址（如 `http://localhost:9011`），导致外部无法直接访问图片。

**修复内容：**
1. **MinIOUploader 构造函数**：添加 `public_base_url` 参数
2. **URL生成逻辑**：所有上传文件的公开URL现在使用 `public_base_url`
3. **配置集成**：从 `config.json` 中读取 `public_base_url` 配置
4. **内容替换**：文章内容中的图片URL替换为公开访问地址

**配置示例：**
```json
{
  "oss": {
    "base_url": "http://localhost:9011",           // 后端API地址（内部调用）
    "public_base_url": "http://60.205.160.74:9000", // 公开访问地址（外部访问）
    "bucket_name": "newsletter-articles-nlp"
  }
}
```

**修复后效果：**
- 上传前：图片URL为 `images/img_0.jpg`（相对路径）
- 上传后：图片URL为 `http://60.205.160.74:9000/bucket-name/articles/article-id/images/img_0.jpg`（公开访问URL）

**验证方法：**
```bash
# 重新上传文章以应用修复
python3 main.py upload --bucket test-public-fix --no-resume

# 检查上传后的文章内容
# 所有图片URL应该使用 public_base_url
```

## 更新日志

### v2.2 (2024-08-07)
- 🔧 **重大修复**: 修复图片URL替换逻辑，避免重复替换导致的嵌套URL问题
- ✅ 改进 `replace_image_urls` 方法，使用精确的正则表达式匹配
- ✅ 按路径长度排序处理，避免部分匹配冲突
- ✅ 增强对Markdown图片语法 `![](path)` 的支持
- ✅ 防止已替换URL被二次处理

### v2.1 (2024-08-07)
- 🔧 **重要修复**: 图片URL使用公开访问地址而非后端API地址
- ✅ MinIOUploader添加public_base_url参数
- ✅ 所有文件上传后返回公开可访问的URL
- ✅ 文章内容中的图片路径替换为公开URL
- ✅ 配置文件支持独立的后端和公开访问地址

### v2.0 (2024-08)
- ✅ 重构为模块化架构
- ✅ 添加断点续传功能
- ✅ 优化并发上传性能
- ✅ 增强错误处理和重试机制
- ✅ 支持自定义bucket名称
- ✅ 添加上传进度监控

### v1.0 (2024-07) 
- ✅ 基础上传功能
- ✅ MinIO集成
- ✅ 简单错误处理