# OSS Upload Module

## 概述

本模块实现了将爬虫数据上传到 MinIO OSS 存储的完整功能，包括：
- 自动创建和配置存储桶
- 批量并发上传文件
- 图片URL自动替换为公开访问地址
- 断点续传和进度追踪
- 错误重试机制

## 配置

在 `config.json` 中配置 OSS 参数：

```json
{
  "oss": {
    "base_url": "http://localhost:9011",      // OSS API 地址
    "public_base_url": "http://localhost:9000", // 公开访问地址
    "bucket_name": "newsletter-articles-nlp",  // 存储桶名称（可配置）
    "source_id": "nlp-elvissaravia",          // 数据源标识
    "max_concurrent_uploads": 10,              // 最大并发上传数
    "upload_timeout": 60,                      // 上传超时（秒）
    "retry_attempts": 3                        // 重试次数
  }
}
```

## 使用方法

### 基本使用

```bash
# 上传所有爬虫数据（默认从 crawled_data 目录）
python3 upload_to_oss.py

# 指定数据目录
python3 upload_to_oss.py --data-dir my_crawled_data

# 使用自定义存储桶名称
python3 upload_to_oss.py --bucket-name my-custom-bucket
```

### 单篇文章上传

```bash
# 上传特定文章
python3 upload_to_oss.py --article-slug "getting-started-with-nlp"
```

### 管理功能

```bash
# 测试 OSS 连接
python3 upload_to_oss.py --test

# 列出所有存储桶
python3 upload_to_oss.py --list-buckets

# 查看上传进度
python3 upload_to_oss.py --show-progress

# 重新开始上传（不使用断点续传）
python3 upload_to_oss.py --no-resume

# 启用详细日志
python3 upload_to_oss.py --verbose
```

## 数据组织结构

### 本地目录结构
```
crawled_data/
├── articles/
│   └── {article_slug}/
│       ├── content.md          # 文章内容
│       ├── metadata.json       # 文章元数据
│       └── images/
│           ├── cover.jpg       # 封面图片
│           └── img_*.jpg       # 内容图片
└── data/
    ├── articles_metadata.json  # 所有文章元数据
    ├── processed_articles.json # 处理后的文章数据
    └── recommendation_data.json # 推荐系统数据
```

### OSS 存储结构
```
{bucket_name}/
├── articles/
│   └── {article_slug}/
│       ├── content.md          # 更新后的内容（图片URL已替换）
│       ├── metadata.json       # 更新后的元数据（包含公开URL）
│       └── images/
│           ├── cover.jpg
│           └── img_*.jpg
└── global/
    ├── articles_metadata.json
    ├── processed_articles.json
    └── recommendation_data.json
```

## 功能特点

### 1. 自动URL替换

上传时自动将Markdown中的本地图片引用替换为OSS公开URL：

**原始内容：**
```markdown
![Cover](images/cover.jpg)
```

**替换后：**
```markdown
![Cover](http://localhost:9000/newsletter-articles-nlp/articles/article-slug/images/cover.jpg)
```

### 2. 断点续传

- 自动保存上传进度到 `oss_upload_progress.json`
- 支持中断后从上次位置继续上传
- 使用 `--no-resume` 参数可重新开始

### 3. 并发上传

- 默认10个并发连接
- 自动批量处理文章
- 图片并发上传优化

### 4. 错误处理

- 自动重试失败的上传（默认3次）
- 指数退避策略
- 详细的错误日志记录

## 公开访问URL格式

上传完成后，文件可通过以下格式的URL公开访问：

```
http://localhost:9000/{bucket_name}/articles/{article_slug}/content.md
http://localhost:9000/{bucket_name}/articles/{article_slug}/metadata.json
http://localhost:9000/{bucket_name}/articles/{article_slug}/images/{image_name}
http://localhost:9000/{bucket_name}/global/{data_file}.json
```

## 测试

运行测试脚本验证功能：

```bash
# 运行所有测试
python3 test_oss_upload.py
```

测试包括：
- URL替换功能测试
- 存储桶名称验证
- OSS连接测试
- 完整上传流程测试

## 注意事项

1. **存储桶命名规则**：
   - 3-63个字符
   - 只能包含小写字母、数字和连字符
   - 必须以字母或数字开头和结尾
   - 不能包含连续的连字符

2. **权限设置**：
   - 所有存储桶自动设置为公开读取
   - 确保不上传敏感信息

3. **性能优化**：
   - 大量文件建议分批上传
   - 可调整 `max_concurrent_uploads` 参数

4. **错误恢复**：
   - 上传失败的文件记录在进度文件中
   - 可查看 `--show-progress` 了解失败详情