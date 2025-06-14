#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
本地化功能的单元测试
"""

import unittest
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ui_zero.localization import (
    get_text,
    get_language,
    set_language,
    is_chinese,
    is_english,
    LocalizationManager,
    nget_text,
)


class TestLocalization(unittest.TestCase):
    """本地化功能测试类"""

    def setUp(self):
        """测试前准备"""
        self.manager = LocalizationManager()
        # 保存原始语言设置
        self.original_language = get_language()

    def tearDown(self):
        """测试后清理"""
        # 恢复原始语言设置
        set_language(self.original_language)

    def test_language_detection(self):
        """测试语言检测功能"""
        # 测试语言检测是否返回有效值
        detected_lang = self.manager._detect_system_language()
        self.assertIn(detected_lang, ["zh_CN", "en_US"])

    def test_language_setting(self):
        """测试语言设置功能"""
        # 测试设置中文
        set_language("zh_CN")
        self.assertEqual(get_language(), "zh_CN")
        self.assertTrue(is_chinese())
        self.assertFalse(is_english())

        # 测试设置英文
        set_language("en_US")
        self.assertEqual(get_language(), "en_US")
        self.assertFalse(is_chinese())
        self.assertTrue(is_english())

    def test_chinese_translations(self):
        """测试中文翻译"""
        set_language("zh_CN")

        # 测试基本翻译
        self.assertEqual(get_text("using_default_device"), "使用默认设备")
        self.assertEqual(get_text("available_devices"), "可用的Android设备:")
        self.assertEqual(
            get_text("cli_description"), "UI-Zero: AI驱动的UI自动化测试工具"
        )

        # 测试带参数的翻译
        result = get_text("starting_task", 1, "test command")
        self.assertEqual(result, "==> 开始执行任务【1】: test command <==")

        result = get_text("task_completed", 2)
        self.assertEqual(result, "任务【2】执行完毕。\n")

    def test_english_translations(self):
        """测试英文翻译"""
        set_language("en_US")

        # 测试基本翻译
        self.assertEqual(get_text("using_default_device"), "Using default device")
        self.assertEqual(get_text("available_devices"), "Available Android devices:")
        self.assertEqual(
            get_text("cli_description"), "UI-Zero: AI-powered UI automation testing"
        )

        # 测试带参数的翻译
        result = get_text("starting_task", 1, "test command")
        self.assertEqual(result, "==> Starting task [1]: test command <==")

        result = get_text("task_completed", 2)
        self.assertEqual(result, "Task [2] completed.\n")

    def test_fallback_behavior(self):
        """测试回退行为"""
        set_language("zh_CN")

        # 测试未定义的消息应该返回原始消息
        undefined_msg = "undefined_message_key"
        result = get_text(undefined_msg)
        self.assertEqual(result, undefined_msg)

        # 测试带参数的未定义消息
        result = get_text(undefined_msg, "param1", "param2")
        # 如果格式化失败，应该返回原始消息
        self.assertEqual(result, undefined_msg)

    def test_parameter_formatting(self):
        """测试参数格式化"""
        set_language("zh_CN")

        # 测试位置参数
        result = get_text("device_list_error", "Connection failed")
        self.assertEqual(result, "获取设备列表失败: Connection failed")

        # 测试多个参数
        result = get_text("loaded_from_file", "test.json", 5)
        self.assertEqual(result, "从文件 'test.json' 加载了 5 个测试用例")

    def test_error_handling(self):
        """测试错误处理"""
        set_language("zh_CN")

        # 测试格式化错误时的处理
        # 如果翻译文本的格式占位符与提供的参数不匹配，应该优雅处理
        try:
            result = get_text("using_default_device", "extra_param")
            # 应该返回翻译后的文本，忽略多余参数
            self.assertEqual(result, "使用默认设备")
        except Exception:
            self.fail("get_text should handle extra parameters gracefully")

    def test_singleton_pattern(self):
        """测试单例模式"""
        manager1 = LocalizationManager()
        manager2 = LocalizationManager()
        self.assertIs(manager1, manager2)

    def test_ngettext_functionality(self):
        """测试复数形式功能（如果需要的话）"""
        set_language("en_US")

        # 注意: 当前的翻译文件没有复数形式，这个测试主要验证函数不会崩溃
        result = nget_text("file", "files", 1)
        self.assertIsInstance(result, str)

        result = nget_text("file", "files", 2)
        self.assertIsInstance(result, str)


class TestLocalizationIntegration(unittest.TestCase):
    """本地化集成测试"""

    def test_environment_language_detection(self):
        """测试环境变量语言检测"""
        manager = LocalizationManager()

        # 测试在不同环境变量下的语言检测
        original_lang = os.environ.get("LANG")

        try:
            # 测试中文环境
            os.environ["LANG"] = "zh_CN.UTF-8"
            detected = manager._detect_system_language()
            self.assertEqual(detected, "zh_CN")

            # 测试英文环境
            os.environ["LANG"] = "en_US.UTF-8"
            detected = manager._detect_system_language()
            self.assertEqual(detected, "en_US")

        finally:
            # 恢复原始环境变量
            if original_lang is not None:
                os.environ["LANG"] = original_lang
            elif "LANG" in os.environ:
                del os.environ["LANG"]

    def test_mo_files_exist(self):
        """测试.mo文件是否存在"""
        locale_dir = project_root / "ui_zero" / "locale"

        zh_mo = locale_dir / "zh_CN" / "LC_MESSAGES" / "ui_zero.mo"
        en_mo = locale_dir / "en_US" / "LC_MESSAGES" / "ui_zero.mo"

        self.assertTrue(zh_mo.exists(), f"Chinese .mo file should exist at {zh_mo}")
        self.assertTrue(en_mo.exists(), f"English .mo file should exist at {en_mo}")

        # 检查文件大小（应该不为空）
        self.assertGreater(
            zh_mo.stat().st_size, 0, "Chinese .mo file should not be empty"
        )
        self.assertGreater(
            en_mo.stat().st_size, 0, "English .mo file should not be empty"
        )


def run_manual_test():
    """手动测试函数，用于开发调试"""
    print("=== 手动测试gettext本地化系统 ===")
    print("当前检测到的系统语言:", get_language())
    print("是否中文环境:", is_chinese())
    print("是否英文环境:", is_english())

    print("\n=== 测试中文输出 ===")
    set_language("zh_CN")
    print("语言设置为:", get_language())
    print(get_text("starting_test_execution"), "5")
    print(get_text("using_default_device"))
    print(get_text("available_devices"))
    print(get_text("cli_description"))

    print("\n=== 测试英文输出 ===")
    set_language("en_US")
    print("语言设置为:", get_language())
    print(get_text("starting_test_execution"), "5")
    print(get_text("using_default_device"))
    print(get_text("available_devices"))
    print(get_text("cli_description"))

    print("\n=== 测试带参数的消息 ===")
    set_language("zh_CN")
    print(get_text("starting_task", 1, "test command"))
    print(get_text("task_completed", 1))

    set_language("en_US")
    print(get_text("starting_task", 1, "test command"))
    print(get_text("task_completed", 1))

    print("\n=== 测试未找到的消息 ===")
    print("未定义消息:", get_text("undefined_message"))


if __name__ == "__main__":
    # 如果直接运行此文件，可以选择运行单元测试或手动测试
    import argparse

    parser = argparse.ArgumentParser(description="本地化测试")
    parser.add_argument("--manual", action="store_true", help="运行手动测试")
    args = parser.parse_args()

    if args.manual:
        run_manual_test()
    else:
        unittest.main()
