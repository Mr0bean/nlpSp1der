# -*- coding: utf-8 -*-
"""
Newsletter 爬虫核心模块。

职责概览：
- 获取文章元数据（分页抓取 API 列表）。
- 使用 Playwright 渲染页面并抽取正文 HTML，再按需转为 Markdown。
- 并发下载封面与正文内图片，替换正文中的图片引用为相对路径。
- 生成每篇文章的 `content.md` 与 `metadata.json`，并输出全量统计。
- 通过 `ProgressTracker` 实现断点续传（记录已处理文章、失败原因、已下载图片）。

实现要点：
- 网络层：使用 `aiohttp` 统一请求与超时控制；图片下载单独限流。
- 浏览器层：维护页面池，避免频繁创建销毁页面导致性能抖动。
- 并发控制：文章与图片分别使用 `asyncio.Semaphore` 控制上限。
- 健壮性：API/页面抓取采用指数退避重试；限流时动态延迟。

使用示例：
    async with NewsletterCrawler(CrawlerConfig(...)) as crawler:
        stats = await crawler.crawl_all()

依赖说明：
- 可选依赖缺失时会进行提示（如 `aiohttp`、`aiofiles`、`beautifulsoup4`、`markdownify`、`playwright`）。
"""
import asyncio
import json
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from urllib.parse import urljoin, urlparse
import logging
from functools import wraps
import time
from dataclasses import dataclass, field
from asyncio import Semaphore

# 尝试导入可选依赖
try:
    import aiohttp
    from aiohttp import ClientTimeout, TCPConnector
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    print("警告: aiohttp 未安装，请运行 'pip install aiohttp' 安装")

try:
    import aiofiles
    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False
    print("警告: aiofiles 未安装，请运行 'pip install aiofiles' 安装")

try:
    from playwright.async_api import async_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("警告: playwright 未安装，请运行 'pip install playwright' 安装")

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("警告: beautifulsoup4 未安装，请运行 'pip install beautifulsoup4' 安装")

try:
    from markdownify import markdownify as md
    MARKDOWNIFY_AVAILABLE = True
except ImportError:
    MARKDOWNIFY_AVAILABLE = False
    print("警告: markdownify 未安装，请运行 'pip install markdownify' 安装")

try:
    from tqdm.asyncio import tqdm_asyncio  # noqa: F401  # 预留未来进度展示
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    # 仅提示，不阻断功能
    print("警告: tqdm 未安装，请运行 'pip install tqdm' 安装")

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class CrawlerConfig:
    """爬虫配置类"""
    base_url: str = "https://nlp.elvissaravia.com"
    output_dir: str = "crawled_data"
    max_concurrent_articles: int = 5  # 最大并发文章处理数
    max_concurrent_images: int = 10   # 最大并发图片下载数
    max_retries: int = 3             # 最大重试次数
    retry_delay: float = 1.0         # 重试延迟（秒）
    request_timeout: int = 30        # 请求超时时间（秒）
    api_delay: float = 1.0           # API请求间隔
    article_delay: float = 0.5       # 文章处理间隔
    browser_timeout: int = 30000     # 浏览器超时（毫秒）
    enable_resume: bool = True       # 启用断点续传
    batch_size: int = 10             # 批处理大小
    

@dataclass
class ProgressTracker:
    """进度跟踪器"""
    processed_articles: Set[int] = field(default_factory=set)
    failed_articles: Dict[int, str] = field(default_factory=dict)
    downloaded_images: Set[str] = field(default_factory=set)
    
    def save(self, filepath: Path):
        """保存进度"""
        data = {
            'processed_articles': list(self.processed_articles),
            'failed_articles': self.failed_articles,
            'downloaded_images': list(self.downloaded_images),
            'last_updated': datetime.now().isoformat()
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load(cls, filepath: Path) -> 'ProgressTracker':
        """加载进度"""
        if not filepath.exists():
            return cls()
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return cls(
                processed_articles=set(data.get('processed_articles', [])),
                failed_articles=data.get('failed_articles', {}),
                downloaded_images=set(data.get('downloaded_images', []))
            )
        except Exception as e:
            logger.error(f"加载进度文件失败: {e}")
            return cls()


def retry_async(max_retries: int = 3, delay: float = 1.0):
    """异步重试装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)  # 指数退避
                        logger.warning(f"{func.__name__} 失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"{func.__name__} 最终失败: {e}")
            raise last_exception
        return wrapper
    return decorator


class NewsletterCrawler:
    def __init__(self, config: Optional[CrawlerConfig] = None):
        self.config = config or CrawlerConfig()
        self.base_url = self.config.base_url
        self.api_url = f"{self.base_url}/api/v1/archive"
        self.output_dir = Path(self.config.output_dir)
        self.articles_dir = self.output_dir / "articles"
        self.images_dir = self.output_dir / "images"
        self.data_dir = self.output_dir / "data"
        
        # 创建目录
        for dir_path in [self.articles_dir, self.images_dir, self.data_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # 资源管理
        self.session: Optional[aiohttp.ClientSession] = None
        self.browser = None
        self.playwright = None
        self.page_pool: List[Page] = []
        
        # 并发控制
        self.article_semaphore = Semaphore(self.config.max_concurrent_articles)
        self.image_semaphore = Semaphore(self.config.max_concurrent_images)
        
        # 进度跟踪
        self.progress = ProgressTracker()
        self.progress_file = self.data_dir / "crawler_progress.json"
        
        # 推荐算法相关字段
        self.recommendation_fields = [
            'id', 'title', 'subtitle', 'post_date', 'audience', 'type', 
            'reactions', 'wordcount', 'postTags', 'cover_image', 
            'description', 'canonical_url', 'slug'
        ]
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        # 创建HTTP会话
        timeout = ClientTimeout(total=self.config.request_timeout)
        connector = TCPConnector(limit=100, limit_per_host=30)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        
        # 启动playwright（缺失时直接报错，避免并发信号量为0导致卡死）
        if PLAYWRIGHT_AVAILABLE:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            # 创建页面池 - 根据配置创建足够的页面
            page_count = min(self.config.max_concurrent_articles, 5)  # 最多5个页面
            for _ in range(page_count):
                page = await self.browser.new_page()
                await page.set_viewport_size({'width': 1920, 'height': 1080})
                # 设置页面超时
                page.set_default_timeout(self.config.browser_timeout)
                self.page_pool.append(page)
            logger.info(f"创建了 {page_count} 个浏览器页面")
        else:
            logger.error("Playwright 未安装或不可用。请先安装依赖并执行: 'pip install playwright' 然后 'playwright install chromium'")
            raise RuntimeError("Playwright is required for content crawling. Please install it.")
        
        # 加载进度
        if self.config.enable_resume:
            self.progress = ProgressTracker.load(self.progress_file)
            if self.progress.processed_articles:
                logger.info(f"从上次进度恢复，已处理 {len(self.progress.processed_articles)} 篇文章")
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        # 保存进度
        if self.config.enable_resume:
            self.progress.save(self.progress_file)
        
        # 清理资源
        if self.session:
            await self.session.close()
        
        if self.page_pool:
            for page in self.page_pool:
                await page.close()
        
        if self.browser:
            await self.browser.close()
        
        if self.playwright:
            await self.playwright.stop()
    
    @retry_async(max_retries=3, delay=1.0)
    async def get_all_articles_metadata(self) -> List[Dict[str, Any]]:
        """获取所有文章的元数据"""
        all_articles = []
        offset = 0
        limit = 12
        
        logger.info("开始获取文章列表...")
        
        while True:
            params = {
                'sort': 'new',
                'search': '',
                'offset': offset,
                'limit': limit
            }
            
            async with self.session.get(self.api_url, params=params) as response:
                response.raise_for_status()
                articles = await response.json()
                
                if not articles:
                    logger.info("没有更多文章了")
                    break
                
                all_articles.extend(articles)
                logger.info(f"已获取 {len(all_articles)} 篇文章")
                
                offset += limit
                await asyncio.sleep(self.config.api_delay)
        
        logger.info(f"总共获取到 {len(all_articles)} 篇文章")
        return all_articles
    
    @retry_async(max_retries=3, delay=0.5)
    async def download_image(self, image_url: str, save_path: Path) -> Optional[Dict[str, Any]]:
        """下载图片到指定路径并计算hash"""
        # 检查是否已下载
        if image_url in self.progress.downloaded_images:
            if save_path.exists():
                # 计算已存在文件的hash
                hasher = hashlib.sha256()
                async with aiofiles.open(save_path, 'rb') as f:
                    content = await f.read()
                    hasher.update(content)
                return {
                    'path': str(save_path.relative_to(self.articles_dir.parent)),
                    'hash': hasher.hexdigest(),
                    'size': len(content)
                }
        
        async with self.image_semaphore:
            try:
                async with self.session.get(image_url) as response:
                    response.raise_for_status()
                    
                    # 确保目录存在
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    content = await response.read()
                    
                    # 计算hash
                    hasher = hashlib.sha256()
                    hasher.update(content)
                    
                    async with aiofiles.open(save_path, 'wb') as f:
                        await f.write(content)
                    
                    self.progress.downloaded_images.add(image_url)
                    return {
                        'path': str(save_path.relative_to(self.articles_dir.parent)),
                        'hash': hasher.hexdigest(),
                        'size': len(content)
                    }
                    
            except Exception as e:
                logger.error(f"下载图片失败 {image_url}: {e}")
                return None
    
    async def download_images_batch(self, image_urls: List[tuple]) -> List[Optional[Dict[str, Any]]]:
        """批量下载图片"""
        tasks = []
        for url, save_path in image_urls:
            task = self.download_image(url, save_path)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        downloaded = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"批量下载图片失败: {result}")
                downloaded.append(None)
            else:
                downloaded.append(result)
        
        return downloaded
    
    def extract_images_from_html(self, html_content: str) -> List[str]:
        """从HTML内容中提取图片URL"""
        soup = BeautifulSoup(html_content, 'html.parser')
        images = []
        
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if src:
                # 处理相对URL
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = urljoin(self.base_url, src)
                elif not src.startswith(('http://', 'https://')):
                    src = urljoin(self.base_url, src)
                images.append(src)
        
        return images
    
    async def get_article_content_with_page(self, article_url: str, page: Page, retry_count: int = 0) -> Optional[str]:
        """使用指定的页面获取文章内容，支持重试"""
        max_retries = 3
        base_delay = 2.0  # 基础延迟（秒）
        
        try:
            # 如果是重试，添加指数退避延迟
            if retry_count > 0:
                delay = base_delay * (2 ** (retry_count - 1))
                logger.info(f"重试 {retry_count}/{max_retries}，等待 {delay} 秒...")
                await asyncio.sleep(delay)
            
            response = await page.goto(article_url, wait_until='networkidle', timeout=self.config.browser_timeout)
            
            # 检查HTTP响应状态码
            status_code = response.status if response else None
            
            # 只有真正的HTTP 429才算限流
            if status_code == 429:
                logger.warning(f"检测到真实的HTTP 429限流: {article_url}")
                if retry_count < max_retries:
                    # 限流时等待更长时间
                    await asyncio.sleep(10)
                    return await self.get_article_content_with_page(article_url, page, retry_count + 1)
                else:
                    logger.error(f"超过最大重试次数，限流持续: {article_url}")
                    return None
            
            # 如果状态码不是200也不是429，记录但继续尝试
            if status_code and status_code != 200:
                logger.debug(f"HTTP状态码 {status_code}: {article_url}")
            
            # 获取页面内容
            page_content = await page.content()
            
            # 只检查Cloudflare或真实的限流页面文本
            rate_limit_indicators = [
                'Access denied',
                'Error 1015',
                'You are being rate limited',
                'Too many requests from this IP',
                'Please wait a few minutes'
            ]
            
            if any(indicator in page_content for indicator in rate_limit_indicators):
                logger.warning(f"检测到限流页面: {article_url}")
                if retry_count < max_retries:
                    await asyncio.sleep(10)
                    return await self.get_article_content_with_page(article_url, page, retry_count + 1)
                else:
                    logger.error(f"超过最大重试次数，限流持续: {article_url}")
                    return None
            
            # 检查是否真正需要登录或付费（更严格的条件）
            paywall_indicators = [
                'This post is for paid subscribers',
                'Upgrade to paid',
                'This content is for subscribers only',
                'Become a paid subscriber to read',
                'Available for paid subscribers'
            ]
            
            if any(indicator in page_content for indicator in paywall_indicators):
                logger.warning(f"文章需要付费订阅: {article_url}")
            
            # 等待内容加载 - 优先使用干净的内容选择器
            content_selectors = [
                '.markup',                    # Priority: Clean content only
                '.body.markup',               # Priority: More specific clean content
                'article .markup',            # Priority: Scoped to article
                'article .body',              # Priority: Alternative within article
                '.single-post-container',     # Fallback selectors
                '.post-content',
                '.entry-content', 
                '.article-content',
                '[data-testid="post-content"]',
                'article',                    # Moved to end - contains UI elements
                'main'
            ]
            
            for selector in content_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    element = await page.query_selector(selector)
                    if element:
                        html_content = await element.inner_html()
                        # 验证内容不为空
                        if html_content and len(html_content) > 100:
                            return html_content
                except:
                    continue
            
            # 如果都找不到，获取body内容
            body = await page.query_selector('body')
            if body:
                html_content = await body.inner_html()
                # 检查是否是有效内容
                if html_content and len(html_content) > 500:
                    return html_content
            
            # 如果内容太少，可能需要重试
            if retry_count < max_retries:
                logger.warning(f"内容过少，尝试重新获取: {article_url}")
                return await self.get_article_content_with_page(article_url, page, retry_count + 1)
                
        except asyncio.TimeoutError:
            logger.error(f"获取文章超时: {article_url}")
            if retry_count < max_retries:
                return await self.get_article_content_with_page(article_url, page, retry_count + 1)
        except Exception as e:
            logger.error(f"获取文章内容失败 {article_url}: {e}")
            if retry_count < max_retries and 'Connection' in str(e):
                # 网络错误时重试
                return await self.get_article_content_with_page(article_url, page, retry_count + 1)
        
        return None
    
    async def process_article_batch(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量处理文章 - 使用信号量限制并发"""
        results = []
        
        # 使用信号量限制并发数，避免页面冲突
        if not self.page_pool:
            raise RuntimeError("No browser pages available. Ensure Playwright is installed and initialized.")
        sem = asyncio.Semaphore(len(self.page_pool))
        
        async def process_with_semaphore(article, index):
            async with sem:
                # 获取一个可用页面
                page = self.page_pool[index % len(self.page_pool)]
                return await self.process_article_with_page(article, page)
        
        # 创建任务
        tasks = [process_with_semaphore(article, i) for i, article in enumerate(articles)]
        
        # 并发执行
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                logger.error(f"处理文章失败 {articles[i].get('id')}: {result}")
                self.progress.failed_articles[articles[i]['id']] = str(result)
            else:
                results.append(result)
        
        return results
    
    async def process_article_with_page(self, article_meta: Dict[str, Any], page: Page) -> Dict[str, Any]:
        """使用指定页面处理单篇文章"""
        article_id = article_meta['id']
        
        # 检查是否已处理
        if self.config.enable_resume and article_id in self.progress.processed_articles:
            logger.info(f"跳过已处理文章: {article_id}")
            return None
        
        async with self.article_semaphore:
            return await self._process_article_internal(article_meta, page)
    
    async def _process_article_internal(self, article_meta: Dict[str, Any], page: Page) -> Dict[str, Any]:
        """内部文章处理逻辑"""
        article_id = article_meta['id']
        title = article_meta.get('title', 'Untitled')
        canonical_url = article_meta.get('canonical_url', '')
        
        logger.info(f"处理文章: {title}")
        
        # 创建安全的文件名和目录名
        safe_title = re.sub(r'[^\w\s-]', '', title).strip()
        safe_title = re.sub(r'[-\s]+', '-', safe_title)[:50]  # 限制长度
        filename = f"{article_id}_{safe_title}"
        
        # 为每篇文章创建独立目录
        article_dir = self.articles_dir / filename
        article_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建图片子目录
        images_dir = article_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
        # 获取文章内容
        html_content = None
        if canonical_url:
            html_content = await self.get_article_content_with_page(canonical_url, page)
        
        # 准备图片下载任务
        image_tasks = []
        
        # 封面图片
        cover_image_info = None
        if article_meta.get('cover_image'):
            cover_url = article_meta['cover_image']
            cover_ext = self._guess_image_extension(cover_url)
            cover_path = images_dir / f"cover{cover_ext}"
            image_tasks.append((cover_url, cover_path))
        
        # 文章中的图片
        article_image_urls = []
        if html_content:
            article_image_urls = self.extract_images_from_html(html_content)
            for i, img_url in enumerate(article_image_urls):
                img_ext = self._guess_image_extension(img_url)
                img_path = images_dir / f"img_{i}{img_ext}"
                image_tasks.append((img_url, img_path))
        
        # 批量下载所有图片
        downloaded_images = await self.download_images_batch(image_tasks)
        
        # 处理下载结果
        if article_meta.get('cover_image') and downloaded_images and downloaded_images[0]:
            cover_image_info = downloaded_images[0]
        
        article_images = []
        if html_content and len(downloaded_images) > 1:
            start_idx = 1 if article_meta.get('cover_image') else 0
            for i, (img_url, img_info) in enumerate(zip(article_image_urls, downloaded_images[start_idx:])):
                if img_info:
                    article_images.append({
                        'original_url': img_url,
                        'local_path': img_info['path'],
                        'hash': img_info['hash'],
                        'size': img_info['size']
                    })
                    # 替换HTML中的图片链接为相对路径（保留原扩展名）
                    rel_ext = Path(article_images[-1]['local_path']).suffix or '.jpg'
                    relative_path = f"images/img_{i}{rel_ext}"
                    html_content = html_content.replace(img_url, relative_path)
        
        # 转换为Markdown
        markdown_content = ""
        if html_content and MARKDOWNIFY_AVAILABLE:
            # 只在内容真的太短时才警告
            if len(html_content) < 100:
                logger.warning(f"文章内容过短 ({len(html_content)} 字符): {article_id}")
                markdown_content = md(html_content, heading_style="ATX", strip=['script', 'style'])
                if not markdown_content.strip():
                    markdown_content = "**注意: 未能获取到有效内容**"
            else:
                # 正常转换为Markdown
                markdown_content = md(html_content, heading_style="ATX", strip=['script', 'style'])
        elif not html_content:
            logger.warning(f"未获取到HTML内容: {article_id}")
            markdown_content = "**错误: 未能获取到文章内容**\n\n可能原因:\n- 网络连接问题\n- 文章需要登录访问\n- 文章已被删除"
        
        # 生成Markdown文件内容（只包含正文） - 先创建临时article_data
        temp_article_data = {
            **article_meta,
            'content_markdown': markdown_content
        }
        md_content = self.generate_markdown_file(temp_article_data)
        
        # 计算文章内容的hash
        content_hash = hashlib.sha256(md_content.encode('utf-8')).hexdigest()
        
        # 创建文章的完整数据
        article_data = {
            **article_meta,
            'cover_image_info': cover_image_info,
            'local_images': article_images,
            'content_html': html_content,
            'content_markdown': markdown_content,
            'processed_date': datetime.now().isoformat(),
            'article_directory': str(article_dir.relative_to(self.output_dir)),
            'content_hash': content_hash
        }
        
        # 保存Markdown文件到文章目录
        md_file_path = article_dir / "content.md"
        async with aiofiles.open(md_file_path, 'w', encoding='utf-8') as f:
            await f.write(md_content)
        
        # 创建元数据（不包含正文内容）
        metadata = {
            'id': article_data.get('id'),
            'title': article_data.get('title'),
            'subtitle': article_data.get('subtitle'),
            'post_date': article_data.get('post_date'),
            'type': article_data.get('type'),
            'wordcount': article_data.get('wordcount'),
            'canonical_url': article_data.get('canonical_url'),
            'slug': article_data.get('slug'),
            'description': article_data.get('description'),
            'reactions': article_data.get('reactions'),
            'audience': article_data.get('audience'),
            'postTags': article_data.get('postTags'),
            'cover_image': cover_image_info,
            'local_images': article_images,
            'article_directory': str(article_dir.relative_to(self.output_dir)),
            'content_hash': content_hash,
            'processed_date': article_data.get('processed_date')
        }
        
        # 保存元数据文件到文章目录
        metadata_file_path = article_dir / "metadata.json"
        async with aiofiles.open(metadata_file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(metadata, ensure_ascii=False, indent=2))
        
        # 标记为已处理
        self.progress.processed_articles.add(article_id)
        
        # 提取推荐算法相关字段
        recommendation_data = {
            field: article_data.get(field) 
            for field in self.recommendation_fields 
            if field in article_data
        }
        
        return {
            'article_data': article_data,
            'recommendation_data': recommendation_data
        }
    
    def generate_markdown_file(self, article_data: Dict[str, Any]) -> str:
        """生成Markdown文件内容 - 只包含正文"""
        md_content = []
        
        # 标题
        md_content.append(f"# {article_data.get('title', 'Untitled')}")
        md_content.append("")
        
        # 副标题
        if article_data.get('subtitle'):
            md_content.append(f"### {article_data.get('subtitle')}")
            md_content.append("")
        
        # 正文内容 - 修复内容中的图片路径
        if article_data.get('content_markdown'):
            # 修复正文中的图片路径
            content_markdown = article_data['content_markdown']
            # 图片路径已经在HTML阶段处理为相对路径 images/img_x.jpg
            
            # 清理掉文章开头的分享按钮、订阅信息等非正文内容
            lines = content_markdown.split('\n')
            cleaned_lines = []
            skip_until_main_content = True
            
            for i, line in enumerate(lines):
                # 检测到真正的文章内容开始
                if skip_until_main_content:
                    # 检查是否是真正的内容开始
                    # 1. 检查是否有实质内容（长度超过20字符且不是UI元素）
                    stripped_line = line.strip()
                    if len(stripped_line) > 20 and not any(skip_word in stripped_line for skip_word in 
                        ['Share this post', 'Copy link', 'Facebook', 'Email', 'Discover more from', 
                         'Subscribe', 'Notes', 'More', 'Already have an account']):
                        skip_until_main_content = False
                        cleaned_lines.append(line)
                    # 2. 或者检测到标题
                    elif stripped_line.startswith('## ') and 'Share this post' not in stripped_line:
                        skip_until_main_content = False
                        cleaned_lines.append(line)
                    # 3. 或者检测到论文标题编号
                    elif stripped_line.startswith('1).') or stripped_line.startswith('1.'):
                        skip_until_main_content = False
                        cleaned_lines.append(line)
                else:
                    # 已经开始正文，过滤UI元素
                    # 跳过重复的分享按钮部分
                    if any(skip_word in line for skip_word in 
                           ['Share this post', 'Copy link', 'Facebook', 'Email']):
                        continue
                    # 跳过订阅相关内容
                    if any(skip_word in line for skip_word in 
                           ['Discover more from', 'Subscribe', 'Already have an account']):
                        continue
                    # 跳过页面导航元素
                    if line.strip() in ['Notes', 'More', 'Share', '[Share](javascript:void(0))']:
                        continue
                    
                    cleaned_lines.append(line)
            
            # 如果没有找到内容开始点，则保留所有不是UI元素的内容
            if not cleaned_lines and content_markdown:
                for line in lines:
                    if not any(skip_word in line for skip_word in 
                              ['Share this post', 'Copy link', 'Facebook', 'Email', 
                               'Discover more from', 'Subscribe', 'Notes', 'More', 
                               'Already have an account', '[Share](javascript:void(0))']):
                        if line.strip():  # 跳过空行
                            cleaned_lines.append(line)
            
            content_markdown = '\n'.join(cleaned_lines).strip()
            md_content.append(content_markdown)
            md_content.append("")
        
        return "\n".join(md_content)

    def _guess_image_extension(self, url: str) -> str:
        """根据 URL 猜测图片扩展名，默认为 .jpg"""
        try:
            parsed = urlparse(url)
            suffix = Path(parsed.path).suffix.lower()
            if suffix in {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}:
                return suffix
        except Exception:
            pass
        return '.jpg'
    
    async def crawl_all(self) -> Dict[str, Any]:
        """爬取所有文章"""
        start_time = time.time()
        logger.info("开始爬取所有文章...")
        
        # 获取所有文章元数据
        articles_metadata = await self.get_all_articles_metadata()
        
        if not articles_metadata:
            logger.error("没有获取到任何文章")
            return {}
        
        # 保存原始元数据
        metadata_file = self.data_dir / "articles_metadata.json"
        async with aiofiles.open(metadata_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(articles_metadata, ensure_ascii=False, indent=2))
        
        # 过滤已处理的文章
        if self.config.enable_resume:
            articles_to_process = [
                article for article in articles_metadata 
                if article['id'] not in self.progress.processed_articles
            ]
            logger.info(f"需要处理 {len(articles_to_process)} 篇新文章")
        else:
            articles_to_process = articles_metadata
        
        # 分批处理文章
        processed_articles = []
        recommendation_data = []
        rate_limit_count = 0  # 限流计数器
        
        for i in range(0, len(articles_to_process), self.config.batch_size):
            batch = articles_to_process[i:i + self.config.batch_size]
            logger.info(f"处理批次 {i//self.config.batch_size + 1}/{(len(articles_to_process) + self.config.batch_size - 1)//self.config.batch_size}")
            
            batch_results = await self.process_article_batch(batch)
            
            # 检查批次结果并处理限流
            has_rate_limit = False
            for result in batch_results:
                if result:
                    article_data = result['article_data']
                    # 检查是否有限流错误
                    if article_data.get('content_markdown') and 'Too Many Requests' in article_data['content_markdown']:
                        has_rate_limit = True
                        rate_limit_count += 1
                        logger.warning(f"文章 {article_data.get('id')} 遇到限流")
                    
                    processed_articles.append(article_data)
                    recommendation_data.append(result['recommendation_data'])
            
            # 定期保存进度
            if self.config.enable_resume:
                self.progress.save(self.progress_file)
            
            # 动态调整延迟
            if has_rate_limit:
                # 限流时增加延迟
                delay = min(30, self.config.article_delay * (2 ** rate_limit_count))
                logger.warning(f"检测到限流，等待 {delay} 秒...")
                await asyncio.sleep(delay)
            else:
                # 正常延迟
                rate_limit_count = 0  # 重置限流计数
                await asyncio.sleep(self.config.article_delay)
        
        # 保存处理后的数据
        processed_file = self.data_dir / "processed_articles.json"
        async with aiofiles.open(processed_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(processed_articles, ensure_ascii=False, indent=2))
        
        # 保存推荐算法数据
        recommendation_file = self.data_dir / "recommendation_data.json"
        async with aiofiles.open(recommendation_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(recommendation_data, ensure_ascii=False, indent=2))
        
        # 生成统计信息
        elapsed_time = time.time() - start_time
        stats = {
            'total_articles': len(articles_metadata),
            'processed_articles': len(processed_articles),
            'failed_articles': len(self.progress.failed_articles),
            'total_images': sum(len(article.get('local_images', [])) for article in processed_articles),
            'downloaded_images': len(self.progress.downloaded_images),
            'crawl_date': datetime.now().isoformat(),
            'elapsed_time': f"{elapsed_time:.2f}秒",
            'output_directory': str(self.output_dir)
        }
        
        stats_file = self.data_dir / "crawl_stats.json"
        async with aiofiles.open(stats_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(stats, ensure_ascii=False, indent=2))
        
        logger.info(f"爬取完成! 处理了 {stats['processed_articles']}/{stats['total_articles']} 篇文章")
        logger.info(f"失败 {stats['failed_articles']} 篇")
        logger.info(f"下载了 {stats['downloaded_images']} 张图片")
        logger.info(f"总耗时: {stats['elapsed_time']}")
        logger.info(f"数据保存在: {self.output_dir}")
        
        return stats


async def main():
    """主函数"""
    # 自定义配置
    config = CrawlerConfig(
        max_concurrent_articles=5,
        max_concurrent_images=20,
        enable_resume=True,
        batch_size=10
    )
    
    async with NewsletterCrawler(config) as crawler:
        stats = await crawler.crawl_all()
        print(f"爬取统计: {json.dumps(stats, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())