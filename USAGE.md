# Newsletter Crawler 使用指南

## 🎯 快速开始

本项目已经整合了所有功能到一个统一的入口 `main.py`，提供了清晰的命令行接口。

## 📁 项目结构

```
爬虫mlp/
├── main.py                 # 统一入口程序 ⭐
├── config.json             # 配置文件
├── src/                    # 源代码
│   └── newsletter_system/
│       ├── crawler/        # 爬虫核心代码
│       ├── oss/           # OSS上传模块
│       └── utils/         # 工具函数
├── scripts/               
│   └── auto_workflow.sh   # 自动化工作流脚本
└── crawled_data/          # 爬取的数据
    ├── articles/          # 文章内容
    ├── images/           # 图片
    └── data/            # 元数据
```

## 🚀 主要功能

### 1. 爬取文章 (crawl)

```bash
# 基本爬取
python3 main.py crawl

# 自定义参数
python3 main.py crawl \
    --concurrent 5 \              # 并发文章数
    --concurrent-images 20 \      # 并发图片数
    --batch-size 10 \             # 批处理大小
    --api-delay 1.0 \            # API请求延迟
    --article-delay 0.5 \        # 文章处理延迟
    --no-resume                  # 不使用断点续传
```

### 2. 检查空内容 (check)

检查哪些文章没有正确爬取到内容：

```bash
python3 main.py check

# 指定数据目录
python3 main.py check --output my_data
```

### 3. 重新爬取问题文章 (recrawl)

重新爬取检查出的空内容文章：

```bash
# 重新爬取所有问题文章
python3 main.py recrawl

# 只重新爬取前10篇
python3 main.py recrawl --max 10
```

### 4. 删除空内容文章 (delete)

删除有问题的文章，为重新爬取做准备：

```bash
# 预览将删除的文章（不实际删除）
python3 main.py delete --dry-run

# 实际删除
python3 main.py delete
```

### 5. 上传到OSS (upload)

将爬取的数据上传到MinIO OSS存储：

```bash
# 使用config.json中的配置
python3 main.py upload

# 覆盖bucket名称
python3 main.py upload --bucket my-newsletter-bucket

# 不使用断点续传
python3 main.py upload --no-resume
```

## 🔧 配置文件

配置文件 `config.json` 包含所有参数设置：

```json
{
  "crawler": {
    "base_url": "https://nlp.elvissaravia.com",
    "output_directory": "crawled_data",
    "max_concurrent_articles": 5,
    "max_concurrent_images": 20,
    "enable_resume": false
  },
  "oss": {
    "base_url": "http://localhost:9011",
    "public_base_url": "http://localhost:9000",
    "bucket_name": "newsletter-articles-nlp",
    "max_concurrent_uploads": 10
  }
}
```

## 🎭 典型工作流

### 方式1: 手动执行各步骤

```bash
# 1. 爬取文章
python3 main.py crawl

# 2. 检查是否有空内容
python3 main.py check

# 3. 如果有问题，删除并重新爬取
python3 main.py delete
python3 main.py recrawl

# 4. 上传到OSS
python3 main.py upload
```

### 方式2: 使用自动化脚本

```bash
# 运行完整的自动化工作流
./scripts/auto_workflow.sh
```

这个脚本会：
1. 自动爬取所有文章
2. 检查空内容
3. 询问是否重新爬取问题文章
4. 进行最终检查
5. 询问是否上传到OSS

## 🔍 高级用法

### 组合命令

```bash
# 爬取后立即检查
python3 main.py crawl && python3 main.py check

# 删除问题文章并重新爬取
python3 main.py delete && python3 main.py recrawl

# 完整流程
python3 main.py crawl && \
python3 main.py check && \
python3 main.py delete && \
python3 main.py recrawl && \
python3 main.py upload
```

### 调试模式

```bash
# 启用详细日志
PYTHONUNBUFFERED=1 python3 main.py crawl

# 只爬取少量文章测试
python3 main.py crawl --batch-size 2 --concurrent 1
```

## 📊 输出说明

### 爬取后的数据结构

```
crawled_data/
├── articles/
│   └── {article_id}_{slug}/
│       ├── content.md          # 文章正文(Markdown)
│       ├── metadata.json       # 文章元数据
│       └── images/
│           ├── cover.jpg       # 封面图
│           └── img_*.jpg       # 内容图片
├── data/
│   ├── articles_metadata.json  # 所有文章元数据
│   ├── processed_articles.json # 处理后的文章
│   └── crawler_progress.json   # 爬取进度
└── images/                     # 全局图片目录
```

### 检查结果

运行 `check` 命令后会生成 `problematic_articles.json`，包含：
- `empty_articles`: 完全没有内容的文章
- `minimal_articles`: 内容少于100字的文章

## ❓ 常见问题

### 1. 爬取速度慢
- 减少并发数：`--concurrent 3`
- 增加延迟：`--article-delay 2`

### 2. 内容爬取失败
- 运行检查：`python3 main.py check`
- 重新爬取：`python3 main.py recrawl`

### 3. OSS上传失败
- 检查OSS服务是否运行
- 验证配置：`python3 upload_to_oss.py --test`

### 4. 断点续传
- 爬虫默认支持断点续传
- 使用 `--no-resume` 强制重新开始

## 🛠️ 开发者信息

### 核心模块
- `newsletter_crawler.py`: 爬虫核心逻辑，使用Playwright
- `uploader.py`: OSS上传逻辑，支持并发和断点续传
- `utils.py`: URL替换和工具函数

### 扩展开发
如需添加新功能，可以：
1. 在 `main.py` 中添加新的子命令
2. 在 `src/newsletter_system/` 中添加新模块
3. 更新配置文件支持新参数

## 📝 更新日志

- **v2.0**: 统一入口，整合所有功能到 `main.py`
- **v1.5**: 修复CSS选择器，解决内容爬取问题
- **v1.0**: 初始版本，基础爬虫功能