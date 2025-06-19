#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CLI模块的集成测试
"""

import unittest
import tempfile
import os
import sys
import yaml
import json
from pathlib import Path
from unittest.mock import patch, Mock

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ui_zero.cli import (
    load_yaml_config,
    convert_yaml_to_testcases,
    execute_unified_action
)
from ui_zero.agent import ActionOutput


class TestCLIIntegration(unittest.TestCase):
    """CLI集成测试"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_yaml_processing_pipeline(self):
        """测试完整的YAML处理流程"""
        # 创建测试YAML文件
        test_config = {
            "android": {
                "deviceId": "test_device_123"
            },
            "tasks": [
                {
                    "name": "测试任务1",
                    "continueOnError": False,
                    "flow": [
                        {"ai": "执行AI动作1"},
                        {"wait": 1000},
                        {"aiWaitFor": "等待条件", "timeout": 5000}
                    ]
                },
                {
                    "name": "测试任务2",
                    "continueOnError": True,
                    "flow": [
                        {"aiAssert": "验证条件", "errorMessage": "验证失败"},
                        {"sleep": 500}  # 测试向后兼容性
                    ]
                }
            ]
        }

        yaml_file = os.path.join(self.temp_dir, "test_config.yaml")
        with open(yaml_file, 'w', encoding='utf-8') as f:
            yaml.dump(test_config, f, allow_unicode=True)

        # 步骤1: 加载YAML配置
        loaded_config = load_yaml_config(yaml_file)
        self.assertEqual(loaded_config, test_config)

        # 步骤2: 转换为测试用例
        with patch('ui_zero.cli.get_text') as mock_get_text:
            def mock_get_text_func(key, *args):
                if key == "ai_wait_for_condition":
                    return f"等待条件满足: {args[0]}"
                elif key == "ai_assert_condition":
                    return f"验证: {args[0]}"
                elif key == "unnamed_task":
                    return "未命名任务"
                else:
                    return f"mocked_{key}"
            
            mock_get_text.side_effect = mock_get_text_func
            testcases, device_id = convert_yaml_to_testcases(loaded_config)

        # 验证设备ID
        self.assertEqual(device_id, "test_device_123")

        # 验证测试用例数量和内容
        self.assertEqual(len(testcases), 5)  # 3 + 2 个动作

        # 验证第一个任务的动作
        self.assertEqual(testcases[0]['type'], 'ai_action')
        self.assertEqual(testcases[0]['prompt'], '执行AI动作1')
        self.assertEqual(testcases[0]['taskName'], '测试任务1')
        self.assertEqual(testcases[0]['continueOnError'], False)

        self.assertEqual(testcases[1]['type'], 'wait')
        self.assertEqual(testcases[1]['duration'], 1000)

        self.assertEqual(testcases[2]['type'], 'ai_action')
        self.assertEqual(testcases[2]['prompt'], '等待条件满足: 等待条件')

        # 验证第二个任务的动作
        self.assertEqual(testcases[3]['type'], 'ai_assert')
        self.assertEqual(testcases[3]['prompt'], '验证条件')
        self.assertEqual(testcases[3]['taskName'], '测试任务2')
        self.assertEqual(testcases[3]['continueOnError'], True)

        # 验证sleep转换为wait
        self.assertEqual(testcases[4]['type'], 'wait')
        self.assertEqual(testcases[4]['duration'], 500)

    def test_action_execution_integration(self):
        """测试动作执行集成"""
        # 模拟ADB工具和Agent
        mock_adb = Mock()
        mock_agent = Mock()
        mock_agent.adb = mock_adb

        # 测试wait动作执行
        wait_action = {
            "type": "wait",
            "duration": 100,  # 短时间用于测试
            "taskName": "集成测试等待",
            "continueOnError": False
        }

        with patch('ui_zero.cli.take_action') as mock_take_action, \
             patch('ui_zero.cli.get_text') as mock_get_text:
            
            def mock_get_text_func(key, *args):
                if key == "starting_wait_action":
                    return f"==> 执行步骤 [{args[0]}]: 等待 {args[1]} 毫秒 <=="
                elif key == "wait_action_completed":
                    return f"步骤 [{args[0]}] 等待完成。"
                elif key == "wait_action_content_completed":
                    return f"等待 {args[0]}ms 完成"
                elif key == "wait_action_thought_completed":
                    return f"等待动作完成: {args[0]}毫秒"
                elif key == "wait_callback_description":
                    return f"等待 {args[0]}ms"
                elif key == "execute_wait_action_thought":
                    return f"执行等待动作: {args[0]}毫秒"
                else:
                    return f"mocked_{key}"
            
            mock_get_text.side_effect = mock_get_text_func

            result = execute_unified_action(
                wait_action,
                mock_agent,
            )

            # 验证结果
            self.assertIsInstance(result, ActionOutput)
            self.assertEqual(result.action, "finished")
            self.assertIn("等待 100ms 完成", result.content)

            # 验证take_action被调用
            mock_take_action.assert_called_once()
            call_args = mock_take_action.call_args[0]
            self.assertEqual(call_args[0], mock_adb)  # 第一个参数是adb
            self.assertEqual(call_args[1].action, "wait")  # 第二个参数是ActionOutput

    def test_error_handling_integration(self):
        """测试错误处理集成"""
        # 测试无效的YAML文件
        invalid_yaml = os.path.join(self.temp_dir, "invalid.yaml")
        with open(invalid_yaml, 'w') as f:
            f.write("invalid: yaml: content: [")

        with self.assertRaises(SystemExit):
            load_yaml_config(invalid_yaml)

        # 测试缺少必要字段的配置
        invalid_config = {"android": {"deviceId": "test"}}  # 缺少tasks

        with self.assertRaises(ValueError):
            convert_yaml_to_testcases(invalid_config)

    def test_backward_compatibility(self):
        """测试向后兼容性"""
        # 测试包含sleep动作的旧格式YAML
        old_format_config = {
            "tasks": [
                {
                    "name": "旧格式任务",
                    "flow": [
                        {"sleep": 2000},
                        {"ai": "旧格式AI动作"}
                    ]
                }
            ]
        }

        testcases, device_id = convert_yaml_to_testcases(old_format_config)

        # 验证sleep被转换为wait
        self.assertEqual(testcases[0]['type'], 'wait')
        self.assertEqual(testcases[0]['duration'], 2000)

        # 验证其他动作正常
        self.assertEqual(testcases[1]['type'], 'ai_action')
        self.assertEqual(testcases[1]['prompt'], '旧格式AI动作')

    def test_mixed_action_types(self):
        """测试混合动作类型"""
        mixed_config = {
            "tasks": [
                {
                    "name": "混合动作任务",
                    "continueOnError": False,
                    "flow": [
                        {"ai": "AI动作"},
                        {"aiAction": "AI动作2"},
                        {"wait": 1000},
                        {"sleep": 500},
                        {"aiWaitFor": "等待条件"},
                        {"aiAssert": "断言条件"}
                    ]
                }
            ]
        }

        testcases, device_id = convert_yaml_to_testcases(mixed_config)

        # 验证所有动作都被正确转换
        self.assertEqual(len(testcases), 6)

        # 验证动作类型
        expected_types = ['ai_action', 'ai_action', 'wait', 'wait', 'ai_action', 'ai_assert']
        actual_types = [tc['type'] for tc in testcases]
        self.assertEqual(actual_types, expected_types)

        # 验证wait动作的持续时间
        wait_actions = [tc for tc in testcases if tc['type'] == 'wait']
        self.assertEqual(len(wait_actions), 2)
        self.assertEqual(wait_actions[0]['duration'], 1000)
        self.assertEqual(wait_actions[1]['duration'], 500)  # sleep转换的


if __name__ == '__main__':
    unittest.main()