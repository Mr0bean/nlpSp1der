# -*- coding: utf-8 -*-
"""
增强反爬虫检测的爬虫模块。

在基础 `NewsletterCrawler` 能力上增加：
- 多 UA、视窗尺寸与区域/时区伪装，降低浏览器指纹相似度；
- 可选集成 `playwright-stealth` 进行更隐蔽的自动化特征规避；
- 注入多项反检测脚本（隐藏 webdriver、修改 plugins/languages/chrome 对象、覆写权限查询、伪装 WebGL 指纹、常亮页面状态等）；
- 智能延迟策略：失败/限流后更长等待、批次间随机延迟、指数退避；
- 更保守的并发配置与页面池管理，降低触发风控概率。

使用场景：
- 目标站点启用了较强的反爬/风控机制，基础爬虫易触发 429/验证码/Cloudflare 速率限制。

注意：
- 本模块只扩展采集策略，不改变数据存储结构与输出契约，兼容上游处理。
- 可选依赖 `playwright-stealth` 缺失时会自动降级为基础反检测功能。
"""

import asyncio
import random
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

from .newsletter_crawler import NewsletterCrawler, CrawlerConfig

# 尝试导入可选依赖
try:
    from playwright.async_api import async_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("警告: playwright 未安装，请运行 'pip install playwright' 安装")

try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    print("提示: playwright-stealth 未安装，将使用基础反检测功能")

logger = logging.getLogger(__name__)


class AntiDetectCrawler(NewsletterCrawler):
    """增强反爬虫检测的爬虫"""
    
    def __init__(self, config: CrawlerConfig):
        super().__init__(config)
        self.user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        self.viewport_sizes = [
            {'width': 1920, 'height': 1080},
            {'width': 1366, 'height': 768},
            {'width': 1440, 'height': 900},
            {'width': 1536, 'height': 864},
            {'width': 1600, 'height': 900}
        ]
        
    async def __aenter__(self):
        """异步上下文管理器入口 - 增强版"""
        await super().__aenter__()
        
        # 重新初始化浏览器，使用更多反爬措施
        if self.browser:
            await self.browser.close()
            
        if self.playwright:
            # 使用增强的浏览器配置（简化参数避免冲突）
            self.browser = await self.playwright.chromium.launch(
                headless=True,  # 可以设置为 False 用于调试
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--window-size=1920,1080',
                ]
            )
            
            # 重新创建页面池，使用反检测措施
            self.page_pool = []
            for i in range(min(self.config.max_concurrent_articles, 3)):
                context = await self.browser.new_context(
                    viewport=random.choice(self.viewport_sizes),
                    user_agent=random.choice(self.user_agents),
                    locale='en-US',
                    timezone_id='America/New_York',
                    permissions=['geolocation'],
                    geolocation={'latitude': 40.7128, 'longitude': -74.0060},
                    color_scheme='light',
                    device_scale_factor=1.0,
                    has_touch=False,
                    is_mobile=False,
                    java_script_enabled=True,
                    bypass_csp=True,
                    ignore_https_errors=True,
                    extra_http_headers={
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Sec-Fetch-User': '?1',
                        'Cache-Control': 'max-age=0',
                    }
                )
                
                page = await context.new_page()
                
                # 应用stealth插件（如果可用）
                if STEALTH_AVAILABLE:
                    await stealth_async(page)
                
                # 注入反检测脚本
                await self.inject_anti_detection_scripts(page)
                
                self.page_pool.append(page)
                
        return self
        
    async def inject_anti_detection_scripts(self, page: Page):
        """注入反检测脚本"""
        scripts = [
            # 移除 webdriver 标记
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            """,
            
            # 修改 navigator.plugins
            """
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {0: {type: "application/x-google-chrome-pdf", suffixes: "pdf"}},
                    {0: {type: "application/pdf", suffixes: "pdf"}}
                ]
            });
            """,
            
            # 修改 navigator.languages
            """
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            """,
            
            # 修改 chrome 对象
            """
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            """,
            
            # 修改权限查询
            """
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            """,
            
            # 修改 WebGL 指纹
            """
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter.apply(this, arguments);
            };
            """,
            
            # 隐藏自动化特征
            """
            Object.defineProperty(document, 'hidden', {
                get: () => false
            });
            Object.defineProperty(document, 'visibilityState', {
                get: () => 'visible'
            });
            """
        ]
        
        for script in scripts:
            try:
                await page.add_init_script(script)
            except Exception as e:
                logger.debug(f"Script injection warning: {e}")
    
    async def get_article_content_with_page(self, article_url: str, page: Page, retry_count: int = 0) -> Optional[str]:
        """增强版文章内容获取，包含更多反爬策略"""
        max_retries = 5  # 增加重试次数
        base_delay = 3.0  # 增加基础延迟
        
        try:
            # 随机延迟（模拟人类行为）
            random_delay = random.uniform(1.5, 4.0)
            await asyncio.sleep(random_delay)
            
            # 如果是重试，使用更长的指数退避延迟
            if retry_count > 0:
                delay = base_delay * (2 ** retry_count) + random.uniform(0, 3)
                logger.info(f"重试 {retry_count}/{max_retries}，等待 {delay:.1f} 秒...")
                await asyncio.sleep(delay)
            
            # 随机化请求头（避免 None 值）
            headers = self.build_random_headers()
            await page.set_extra_http_headers(headers)
            
            # 导航到页面（增加超时时间）
            response = await page.goto(
                article_url, 
                wait_until='domcontentloaded',  # 改为等待DOM加载完成
                timeout=60000  # 增加超时时间到60秒
            )
            
            # 检查响应状态
            if response and response.status == 429:
                logger.warning(f"收到429状态码（限流）: {article_url}")
                if retry_count < max_retries:
                    # 限流时等待更长时间（30-60秒）
                    wait_time = random.uniform(30, 60)
                    logger.info(f"限流等待 {wait_time:.1f} 秒...")
                    await asyncio.sleep(wait_time)
                    return await self.get_article_content_with_page(article_url, page, retry_count + 1)
                else:
                    logger.error(f"超过最大重试次数，限流持续: {article_url}")
                    return None
            
            # 等待一段时间让页面完全加载
            await asyncio.sleep(random.uniform(2, 4))
            
            # 模拟人类行为：随机滚动
            await self.simulate_human_behavior(page)
            
            # 检查页面内容
            page_content = await page.content()
            
            # 检查各种反爬标记
            anti_bot_indicators = [
                'Too Many Requests',
                '429',
                'rate limit',
                'Access Denied',
                'Forbidden',
                'Please verify you are human',
                'Cloudflare',
                'CAPTCHA',
                'cf-browser-verification'
            ]
            
            for indicator in anti_bot_indicators:
                if indicator.lower() in page_content.lower():
                    logger.warning(f"检测到反爬标记 '{indicator}': {article_url}")
                    if retry_count < max_retries:
                        # 遇到反爬时等待更长时间
                        wait_time = random.uniform(20, 40)
                        logger.info(f"反爬等待 {wait_time:.1f} 秒...")
                        await asyncio.sleep(wait_time)
                        
                        # 可能需要刷新页面或使用新的页面
                        if retry_count > 2:
                            # 尝试刷新页面
                            await page.reload(wait_until='domcontentloaded')
                            await asyncio.sleep(random.uniform(3, 5))
                        
                        return await self.get_article_content_with_page(article_url, page, retry_count + 1)
                    else:
                        logger.error(f"超过最大重试次数，仍被检测: {article_url}")
                        return None
            
            # 尝试获取内容（使用父类的逻辑）
            content = await super().get_article_content_with_page(article_url, page, 0)
            
            if content:
                return content
            elif retry_count < max_retries:
                logger.warning(f"未获取到有效内容，重试: {article_url}")
                return await self.get_article_content_with_page(article_url, page, retry_count + 1)
            else:
                logger.error(f"无法获取内容: {article_url}")
                return None
                
        except asyncio.TimeoutError:
            logger.error(f"获取文章超时: {article_url}")
            if retry_count < max_retries:
                # 超时后等待一段时间
                await asyncio.sleep(random.uniform(10, 20))
                return await self.get_article_content_with_page(article_url, page, retry_count + 1)
        except Exception as e:
            logger.error(f"获取文章内容失败 {article_url}: {e}")
            if retry_count < max_retries:
                await asyncio.sleep(random.uniform(5, 10))
                return await self.get_article_content_with_page(article_url, page, retry_count + 1)
        
        return None

    def build_random_headers(self) -> Dict[str, str]:
        """构建随机请求头（不包含 None 值），便于测试与复用"""
        headers: Dict[str, str] = {
            'Referer': 'https://www.google.com/',
            'DNT': '1',
        }
        if random.random() > 0.5:
            headers['X-Requested-With'] = 'XMLHttpRequest'
        return headers
    
    async def simulate_human_behavior(self, page: Page):
        """模拟人类行为"""
        try:
            # 随机滚动页面
            scroll_actions = [
                # 缓慢向下滚动
                "window.scrollBy({top: 300, behavior: 'smooth'})",
                "window.scrollBy({top: 500, behavior: 'smooth'})",
                "window.scrollBy({top: -200, behavior: 'smooth'})",
                # 滚动到特定位置
                "window.scrollTo({top: document.body.scrollHeight * 0.3, behavior: 'smooth'})",
                "window.scrollTo({top: document.body.scrollHeight * 0.6, behavior: 'smooth'})",
            ]
            
            # 执行2-3个随机滚动动作
            num_actions = random.randint(2, 3)
            for _ in range(num_actions):
                action = random.choice(scroll_actions)
                await page.evaluate(action)
                await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # 随机移动鼠标（如果需要）
            if random.random() > 0.7:
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                await page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.1, 0.3))
                
        except Exception as e:
            logger.debug(f"模拟行为异常（可忽略）: {e}")
    
    async def process_articles(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """处理文章列表 - 增强版，包含智能延迟"""
        processed_count = 0
        failed_count = 0
        stats = {
            'total_articles': len(articles),
            'processed_articles': 0,
            'failed_articles': 0,
            'skipped_articles': 0
        }
        
        # 按批次处理，每批之间有更长的延迟
        batch_size = min(3, self.config.batch_size)  # 减小批次大小
        total_batches = (len(articles) + batch_size - 1) // batch_size
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min((batch_idx + 1) * batch_size, len(articles))
            batch = articles[start_idx:end_idx]
            
            logger.info(f"处理批次 {batch_idx + 1}/{total_batches}")
            
            # 处理批次
            for article in batch:
                # 检查是否已处理（统一为 int 类型）
                raw_id = article.get('id')
                try:
                    article_id_int = int(raw_id) if raw_id is not None else None
                except (TypeError, ValueError):
                    article_id_int = None
                if (article_id_int is not None) and (article_id_int in self.progress.processed_articles):
                    logger.info(f"跳过已处理文章: {article_id_int}")
                    stats['skipped_articles'] += 1
                    continue

                # 随机选择一个页面
                page = random.choice(self.page_pool)
                result = await self.process_article_with_page(article, page)

                if result:
                    processed_count += 1
                    stats['processed_articles'] += 1
                    if article_id_int is not None:
                        self.progress.processed_articles.add(article_id_int)
                else:
                    failed_count += 1
                    stats['failed_articles'] += 1
                    if article_id_int is not None:
                        self.progress.failed_articles[article_id_int] = "Processing failed"

                # 保存进度
                if self.config.enable_resume:
                    self.progress.save(self.progress_file)

                # 智能延迟：失败后等待更长时间
                if not result:
                    delay = random.uniform(10, 20)
                    logger.info(f"失败后延迟 {delay:.1f} 秒...")
                else:
                    delay = random.uniform(3, 8)

                await asyncio.sleep(delay)
            
            # 批次间延迟（更长）
            if batch_idx < total_batches - 1:
                batch_delay = random.uniform(15, 30)
                logger.info(f"批次间延迟 {batch_delay:.1f} 秒...")
                await asyncio.sleep(batch_delay)
        
        return stats


from dataclasses import dataclass, field

@dataclass
class EnhancedCrawlerConfig(CrawlerConfig):
    """增强的爬虫配置"""
    use_proxy: bool = False
    proxy_url: Optional[str] = None
    smart_delay: bool = True
    min_delay: float = 3.0
    max_delay: float = 10.0
    batch_delay: float = 20.0
    rate_limit_delay: float = 60.0