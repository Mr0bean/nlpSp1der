# 反爬虫策略指南

## 问题诊断

当前爬虫遇到的反爬问题：
- **429 Too Many Requests** - 请求频率过高
- **Rate Limiting** - 速率限制
- **Browser Detection** - 浏览器检测

## 解决方案

### 1. 使用增强版反爬虫爬虫

```bash
# 安装依赖
pip install playwright-stealth fake-useragent

# 运行反爬虫版本（推荐）
python run_anti_detect.py

# 测试少量文章
python run_anti_detect.py --limit 5

# 极慢速爬取（最安全）
python run_anti_detect.py --concurrent 1 --batch 2 --article-delay 10
```

### 2. 核心反爬策略

#### 🛡️ 浏览器指纹伪装
- 随机User-Agent
- 随机视窗大小
- 注入反检测JavaScript
- 移除webdriver标记
- 模拟真实浏览器插件

#### ⏱️ 智能延迟机制
- **随机延迟**: 1.5-4秒基础延迟
- **指数退避**: 失败后延迟翻倍
- **批次延迟**: 批次间15-30秒
- **限流延迟**: 遇到429后等待30-60秒

#### 🔄 重试策略
- 最多重试5次
- 每次重试延迟递增
- 检测多种反爬标记
- 智能判断是否继续

#### 🎭 人类行为模拟
- 随机页面滚动
- 鼠标移动轨迹
- 不规则访问间隔
- Referer头伪装

### 3. 使用建议

#### 轻度反爬（推荐首选）
```bash
python run_anti_detect.py --concurrent 2 --batch 3
```

#### 中度反爬
```bash
python run_anti_detect.py --concurrent 1 --batch 2 --article-delay 8
```

#### 严重反爬
```bash
# 极慢速 + 单线程
python run_anti_detect.py --concurrent 1 --batch 1 --article-delay 15

# 使用代理
python run_anti_detect.py --use-proxy --proxy-url http://127.0.0.1:7890
```

### 4. 代理配置

如果需要使用代理：

```bash
# HTTP代理
python run_anti_detect.py --use-proxy --proxy-url http://proxy-server:port

# SOCKS5代理
python run_anti_detect.py --use-proxy --proxy-url socks5://proxy-server:port
```

### 5. 断点续传

爬虫支持断点续传，如果中断可以继续：

```bash
# 默认启用断点续传
python run_anti_detect.py

# 强制重新开始
python run_anti_detect.py --no-resume
```

### 6. 监控和调试

查看详细日志：
```bash
# 日志会自动保存到 logs/ 目录
tail -f logs/anti_detect_crawler_*.log
```

### 7. 常见问题

#### Q: 还是被限流怎么办？
A: 
1. 增加延迟：`--article-delay 20`
2. 减少并发：`--concurrent 1`
3. 使用代理池
4. 等待几小时后再试

#### Q: 爬取速度太慢？
A: 这是正常的，反爬策略需要牺牲速度换取成功率。建议：
- 使用断点续传，分多次完成
- 晚上运行，让它慢慢爬
- 部署到服务器24小时运行

#### Q: 如何知道是否被检测？
A: 查看日志中的关键词：
- "检测到限流"
- "检测到反爬标记"
- "429"
- "Too Many Requests"

## 技术原理

### 反检测脚本注入

爬虫会注入以下JavaScript来避免检测：

1. **移除自动化标记**
```javascript
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});
```

2. **伪装插件列表**
```javascript
Object.defineProperty(navigator, 'plugins', {
    get: () => [/* Chrome PDF plugins */]
});
```

3. **修改WebGL指纹**
```javascript
WebGLRenderingContext.prototype.getParameter = /* Intel Graphics */
```

### 请求头优化

每个请求都包含：
- 真实的User-Agent
- 合理的Accept-Language
- Google搜索Referer
- 完整的Sec-Fetch头

## 最佳实践

1. **首次运行**：先用 `--limit 5` 测试
2. **正常爬取**：使用默认参数
3. **被限流后**：等待1小时，使用更慢速度
4. **长期运行**：配置代理池，使用多个IP

## 更新日志

- v1.0: 基础反爬功能
- v1.1: 添加智能延迟
- v1.2: 增强浏览器指纹伪装
- v1.3: 支持代理和人类行为模拟