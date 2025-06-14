#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
本地化支持模块
使用Python标准库gettext和locale实现国际化
"""

import os
import locale
import gettext
from typing import Optional
from pathlib import Path


class LocalizationManager:
    """本地化管理器，使用gettext实现"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LocalizationManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._domain = "ui_zero"
            self._locale_dir = Path(__file__).parent / "locale"
            self._current_language = None
            self._translation = None
            self._setup_localization()
            LocalizationManager._initialized = True

    def _detect_system_language(self) -> str:
        """检测系统语言"""
        try:
            # 1. 优先使用环境变量 LANG
            lang_env = os.environ.get("LANG", "")
            if lang_env.startswith("zh"):
                return "zh_CN"
            elif lang_env.startswith("en"):
                return "en_US"

            # 2. 使用locale模块检测
            try:
                system_locale = locale.getdefaultlocale()[0]
                if system_locale:
                    if system_locale.startswith("zh"):
                        return "zh_CN"
                    elif system_locale.startswith("en"):
                        return "en_US"
            except (ValueError, TypeError):
                pass

            # 3. 检查LC_ALL环境变量
            lc_all = os.environ.get("LC_ALL", "")
            if lc_all.startswith("zh"):
                return "zh_CN"
            elif lc_all.startswith("en"):
                return "en_US"

            # 4. 检查LC_MESSAGES环境变量
            lc_messages = os.environ.get("LC_MESSAGES", "")
            if lc_messages.startswith("zh"):
                return "zh_CN"
            elif lc_messages.startswith("en"):
                return "en_US"

            # 默认使用中文（因为项目主要面向中文用户）
            return "zh_CN"
        except Exception:
            return "zh_CN"

    def _setup_localization(self):
        """设置本地化"""
        # 检测系统语言
        detected_lang = self._detect_system_language()

        # 设置locale（如果可能的话）
        try:
            if detected_lang == "zh_CN":
                # 尝试设置中文locale
                try:
                    locale.setlocale(locale.LC_ALL, "zh_CN.UTF-8")
                except locale.Error:
                    try:
                        locale.setlocale(locale.LC_ALL, "Chinese_China.UTF-8")
                    except locale.Error:
                        pass  # 使用默认locale
            elif detected_lang == "en_US":
                # 尝试设置英文locale
                try:
                    locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
                except locale.Error:
                    try:
                        locale.setlocale(locale.LC_ALL, "English_United States.UTF-8")
                    except locale.Error:
                        pass  # 使用默认locale
        except Exception:
            pass  # 如果locale设置失败，继续使用默认值

        # 设置gettext
        self.set_language(detected_lang)

    def set_language(self, language: str):
        """设置语言"""
        if self._current_language == language and self._translation:
            return

        try:
            # 确保locale目录存在
            if not self._locale_dir.exists():
                # 如果locale目录不存在，使用fallback
                self._translation = gettext.NullTranslations()
                self._current_language = language
                return

            # 加载gettext翻译
            self._translation = gettext.translation(
                self._domain,
                localedir=str(self._locale_dir),
                languages=[language],
                fallback=True,
            )

            self._current_language = language

        except Exception:
            # 如果加载失败，使用fallback
            self._translation = gettext.NullTranslations()
            self._current_language = language

    def get_language(self) -> str:
        """获取当前语言"""
        return self._current_language or "zh_CN"

    def get_text(self, message: str, *args, **kwargs) -> str:
        """获取本地化文本"""
        try:
            if not self._translation:
                translated = message
            else:
                translated = self._translation.gettext(message)

            # 处理格式化参数
            if args or kwargs:
                return translated.format(*args, **kwargs)
            return translated
        except (KeyError, ValueError, AttributeError):
            # 如果格式化失败，返回原始消息
            return message

    def nget_text(self, singular: str, plural: str, n: int, *args, **kwargs) -> str:
        """获取复数形式的本地化文本"""
        try:
            if not self._translation:
                translated = singular if n == 1 else plural
            else:
                translated = self._translation.ngettext(singular, plural, n)

            # 处理格式化参数
            if args or kwargs:
                return translated.format(n, *args, **kwargs)
            return translated.format(n)
        except (KeyError, ValueError, AttributeError):
            # 如果格式化失败，返回原始消息
            return singular if n == 1 else plural

    def is_chinese(self) -> bool:
        """是否为中文环境"""
        return self.get_language().startswith("zh")

    def is_english(self) -> bool:
        """是否为英文环境"""
        return self.get_language().startswith("en")


# 全局实例
_localization_manager = LocalizationManager()


def get_text(message: str, *args, **kwargs) -> str:
    """获取本地化文本的便捷函数"""
    return _localization_manager.get_text(message, *args, **kwargs)


def nget_text(singular: str, plural: str, n: int, *args, **kwargs) -> str:
    """获取复数形式本地化文本的便捷函数"""
    return _localization_manager.nget_text(singular, plural, n, *args, **kwargs)


def set_language(language: str):
    """设置语言的便捷函数"""
    _localization_manager.set_language(language)


def get_language() -> str:
    """获取当前语言的便捷函数"""
    return _localization_manager.get_language()


def is_chinese() -> bool:
    """是否为中文环境的便捷函数"""
    return _localization_manager.is_chinese()


def is_english() -> bool:
    """是否为英文环境的便捷函数"""
    return _localization_manager.is_english()


# 为了兼容性，也可以使用这些函数
_ = get_text  # 标准的gettext别名
ngettext = nget_text  # 标准的ngettext别名
