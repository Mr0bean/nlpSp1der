"""
日志工具。

提供一个简洁的 `setup_logger` 入口，用于配置控制台和可选文件日志输出；
避免在各处重复创建/配置日志器导致重复日志与格式不一致。
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(
    name: str = "newsletter_system",
    level: int = logging.INFO,
    log_file: str = None,
    format_string: str = None
) -> logging.Logger:
    """
    初始化一个带控制台输出且可选写文件的标准日志器。

    参数：
    - name: 日志器名称（同名复用，避免重复创建）。
    - level: 日志级别（logging.INFO / DEBUG / WARNING / ERROR）。
    - log_file: 可选日志文件路径，提供则同时写入文件。
    - format_string: 日志格式字符串；默认包含时间、名称、级别与消息。

    返回：
    - `logging.Logger` 实例。

    示例：
        logger = setup_logger("anti_detect", level=logging.INFO, log_file="logs/anti.log")
        logger.info("crawler started")
    """
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    formatter = logging.Formatter(format_string)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger