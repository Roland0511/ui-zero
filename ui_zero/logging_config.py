#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统一的日志配置模块
将调试和错误日志输出到文件，程序输出通过UI显示系统处理
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO

from .localization import get_text


def ensure_log_directory() -> Path:
    """确保日志目录存在"""
    log_dir = Path.home() / ".uiz" / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def create_log_filename() -> str:
    """创建日志文件名"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"uiz_{timestamp}.log"


class UIZeroFileLogger:
    """UI-Zero文件日志管理器"""

    def __init__(self) -> None:
        self._logger: Optional[logging.Logger] = None
        self._configured = False
        self._log_file: Optional[Path] = None

    def configure(
        self,
        level: int = logging.INFO,
        format_string: Optional[str] = None,
        max_log_files: int = 10,
    ) -> Path:
        """
        配置文件日志系统

        Args:
            level: 日志级别
            format_string: 自定义格式字符串
            max_log_files: 最大保留的日志文件数量

        Returns:
            日志文件路径
        """
        if self._configured:
            return self._log_file

        # 确保日志目录存在
        log_dir = ensure_log_directory()
        
        # 清理旧日志文件
        self._cleanup_old_logs(log_dir, max_log_files)

        # 创建日志文件
        self._log_file = log_dir / create_log_filename()

        # 创建主logger
        self._logger = logging.getLogger("ui_zero")
        self._logger.setLevel(level)

        # 清除现有的handlers
        for handler in self._logger.handlers[:]:
            self._logger.removeHandler(handler)

        # 配置文件handler
        self._configure_file_handler(level, format_string)

        # 禁用第三方库的详细日志
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("PIL").setLevel(logging.WARNING)

        self._configured = True
        return self._log_file

    def _configure_file_handler(self, level: int, format_string: Optional[str]) -> None:
        """配置文件日志handler"""
        if format_string is None:
            format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        formatter = logging.Formatter(format_string)

        # 文件handler
        file_handler = logging.FileHandler(self._log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)

        if self._logger is not None:
            self._logger.addHandler(file_handler)

    def _cleanup_old_logs(self, log_dir: Path, max_files: int) -> None:
        """清理旧的日志文件"""
        log_files = list(log_dir.glob("uiz_*.log"))
        if len(log_files) >= max_files:
            # 按修改时间排序，删除最旧的文件
            log_files.sort(key=lambda x: x.stat().st_mtime)
            files_to_delete = log_files[:-max_files + 1]
            for file_path in files_to_delete:
                try:
                    file_path.unlink()
                except OSError:
                    pass  # 忽略删除失败的情况

    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """
        获取logger实例

        Args:
            name: logger名称，如果为None则返回主logger

        Returns:
            Logger实例
        """
        if not self._configured:
            # 如果未配置，使用默认配置
            self.configure()

        if name is None:
            if self._logger is None:
                raise RuntimeError("Logger not configured properly")
            return self._logger

        # 创建子logger
        child_logger = logging.getLogger(f"ui_zero.{name}")
        if self._logger is not None:
            child_logger.setLevel(self._logger.level)
        return child_logger

    def cleanup(self) -> None:
        """清理日志配置"""
        if self._logger:
            for handler in self._logger.handlers[:]:
                handler.close()
                self._logger.removeHandler(handler)

        self._configured = False
        self._logger = None
        self._log_file = None

    @property
    def log_file(self) -> Optional[Path]:
        """获取当前日志文件路径"""
        return self._log_file

    @property
    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(self._configured)


# 全局日志管理器实例
_log_manager = UIZeroFileLogger()


def configure_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    max_log_files: int = 10,
) -> Path:
    """
    配置全局文件日志系统

    Args:
        level: 日志级别
        format_string: 自定义格式字符串
        max_log_files: 最大保留的日志文件数量

    Returns:
        日志文件路径
    """
    return _log_manager.configure(level, format_string, max_log_files)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取logger实例

    Args:
        name: logger名称

    Returns:
        Logger实例
    """
    return _log_manager.get_logger(name)


def cleanup_logging() -> None:
    """清理日志配置"""
    _log_manager.cleanup()


def get_log_file() -> Optional[Path]:
    """获取当前日志文件路径"""
    return _log_manager.log_file


def is_logging_configured() -> bool:
    """检查日志是否已配置"""
    return _log_manager.is_configured
