#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CLI模块的单元测试
"""

import unittest
import json
import yaml
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from typing import List, Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ui_zero.cli import (
    list_available_devices,
    load_testcase_from_file,
    load_yaml_config,
    convert_yaml_to_testcases,
    execute_wait_action,
    execute_unified_action,
    run_testcases,
    StepRunner,
    execute_single_step,
    run_testcases_for_gui,
)
from ui_zero.agent import ActionOutput, AndroidAgent
from ui_zero.adb import ADBTool


class TestDeviceListing(unittest.TestCase):
    """设备列表功能测试"""

    @patch('ui_zero.cli.ADBTool')
    def test_list_available_devices_success(self, mock_adb_tool):
        """测试成功获取设备列表"""
        # 模拟ADBTool返回设备列表
        mock_instance = Mock()
        mock_instance.get_connected_devices.return_value = ['device1', 'device2']
        mock_adb_tool.return_value = mock_instance

        devices = list_available_devices()
        
        self.assertEqual(devices, ['device1', 'device2'])
        mock_adb_tool.assert_called_once()
        mock_instance.get_connected_devices.assert_called_once()

    @patch('ui_zero.cli.ADBTool')
    @patch('ui_zero.cli.logger')
    def test_list_available_devices_error(self, mock_logger, mock_adb_tool):
        """测试获取设备列表失败"""
        # 模拟ADBTool抛出异常
        mock_adb_tool.side_effect = Exception("ADB error")

        devices = list_available_devices()
        
        self.assertEqual(devices, [])
        mock_logger.error.assert_called_once()


class TestFileLoading(unittest.TestCase):
    """文件加载功能测试"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """测试后清理"""
        # 清理临时文件
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_testcase_from_file_success(self):
        """测试成功加载JSON测试用例文件"""
        test_data = ["test1", "test2", "test3"]
        test_file = os.path.join(self.temp_dir, "test.json")
        
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)

        result = load_testcase_from_file(test_file)
        self.assertEqual(result, test_data)

    def test_load_testcase_from_file_not_found(self):
        """测试加载不存在的文件"""
        with self.assertRaises(SystemExit):
            load_testcase_from_file("nonexistent.json")

    def test_load_testcase_from_file_invalid_json(self):
        """测试加载无效的JSON文件"""
        test_file = os.path.join(self.temp_dir, "invalid.json")
        
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("invalid json content")

        with self.assertRaises(SystemExit):
            load_testcase_from_file(test_file)

    def test_load_testcase_from_file_invalid_format(self):
        """测试加载格式错误的JSON文件"""
        test_file = os.path.join(self.temp_dir, "invalid_format.json")
        
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump({"not": "a list"}, f)

        with self.assertRaises(SystemExit):
            load_testcase_from_file(test_file)

    def test_load_yaml_config_success(self):
        """测试成功加载YAML配置文件"""
        test_data = {
            "android": {"deviceId": "test_device"},
            "tasks": [{"name": "test", "flow": [{"ai": "test action"}]}]
        }
        test_file = os.path.join(self.temp_dir, "test.yaml")
        
        with open(test_file, 'w', encoding='utf-8') as f:
            yaml.dump(test_data, f)

        result = load_yaml_config(test_file)
        self.assertEqual(result, test_data)

    def test_load_yaml_config_not_found(self):
        """测试加载不存在的YAML文件"""
        with self.assertRaises(SystemExit):
            load_yaml_config("nonexistent.yaml")

    def test_load_yaml_config_invalid_yaml(self):
        """测试加载无效的YAML文件"""
        test_file = os.path.join(self.temp_dir, "invalid.yaml")
        
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("invalid: yaml: content: [")

        with self.assertRaises(SystemExit):
            load_yaml_config(test_file)

    def test_load_yaml_config_invalid_format(self):
        """测试加载格式错误的YAML文件"""
        test_file = os.path.join(self.temp_dir, "invalid_format.yaml")
        
        with open(test_file, 'w', encoding='utf-8') as f:
            yaml.dump("not a dict", f)

        with self.assertRaises(SystemExit):
            load_yaml_config(test_file)


class TestYamlToTestcases(unittest.TestCase):
    """YAML转测试用例功能测试"""

    def test_convert_yaml_to_testcases_basic(self):
        """测试基本的YAML转换"""
        config = {
            "android": {"deviceId": "test_device"},
            "tasks": [
                {
                    "name": "test_task",
                    "continueOnError": False,
                    "flow": [
                        {"ai": "test ai action"},
                        {"aiAction": "test aiAction"},
                        {"aiWaitFor": "test condition", "timeout": 5000},
                        {"aiAssert": "test assertion", "errorMessage": "test error"},
                        {"sleep": 1000},
                        {"wait": 2000}
                    ]
                }
            ]
        }

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
            testcases, device_id = convert_yaml_to_testcases(config)

        self.assertEqual(device_id, "test_device")
        self.assertEqual(len(testcases), 6)

        # 检查ai动作
        self.assertEqual(testcases[0]['type'], 'ai_action')
        self.assertEqual(testcases[0]['prompt'], 'test ai action')
        self.assertEqual(testcases[0]['continueOnError'], False)
        self.assertEqual(testcases[0]['taskName'], 'test_task')

        # 检查aiAction动作
        self.assertEqual(testcases[1]['type'], 'ai_action')
        self.assertEqual(testcases[1]['prompt'], 'test aiAction')

        # 检查aiWaitFor动作
        self.assertEqual(testcases[2]['type'], 'ai_action')
        self.assertEqual(testcases[2]['prompt'], '等待条件满足: test condition')

        # 检查aiAssert动作
        self.assertEqual(testcases[3]['type'], 'ai_assert')
        self.assertEqual(testcases[3]['prompt'], 'test assertion')

        # 检查sleep动作转换为wait
        self.assertEqual(testcases[4]['type'], 'wait')
        self.assertEqual(testcases[4]['duration'], 1000)

        # 检查wait动作
        self.assertEqual(testcases[5]['type'], 'wait')
        self.assertEqual(testcases[5]['duration'], 2000)

    def test_convert_yaml_to_testcases_continue_on_error(self):
        """测试continueOnError参数"""
        config = {
            "tasks": [
                {
                    "name": "test_task",
                    "continueOnError": True,
                    "flow": [{"ai": "test action"}]
                }
            ]
        }

        testcases, device_id = convert_yaml_to_testcases(config)

        self.assertIsNone(device_id)
        self.assertEqual(len(testcases), 1)
        self.assertEqual(testcases[0]['continueOnError'], True)

    def test_convert_yaml_to_testcases_no_device_id(self):
        """测试没有设备ID的情况"""
        config = {
            "tasks": [
                {
                    "name": "test_task",
                    "flow": [{"ai": "test action"}]
                }
            ]
        }

        testcases, device_id = convert_yaml_to_testcases(config)

        self.assertIsNone(device_id)
        self.assertEqual(testcases[0]['continueOnError'], False)  # 默认值

    def test_convert_yaml_to_testcases_missing_tasks(self):
        """测试缺少tasks字段的情况"""
        config = {"android": {"deviceId": "test"}}

        with self.assertRaises(ValueError):
            convert_yaml_to_testcases(config)

    def test_convert_yaml_to_testcases_invalid_tasks(self):
        """测试无效的tasks字段"""
        config = {"tasks": "not a list"}

        with self.assertRaises(ValueError):
            convert_yaml_to_testcases(config)

    def test_convert_yaml_to_testcases_empty_tasks(self):
        """测试空的tasks列表"""
        config = {"tasks": []}

        testcases, device_id = convert_yaml_to_testcases(config)

        self.assertEqual(testcases, [])
        self.assertIsNone(device_id)

    def test_convert_yaml_to_testcases_invalid_task_format(self):
        """测试无效的任务格式"""
        config = {
            "tasks": [
                "invalid task",  # 不是字典
                {"name": "valid", "flow": []},  # 有效任务
                {"flow": [{"ai": "no name"}]}  # 缺少name字段
            ]
        }

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
            testcases, device_id = convert_yaml_to_testcases(config)

        # 应该跳过无效任务，只处理有效任务
        self.assertEqual(len(testcases), 1)
        self.assertEqual(testcases[0]['taskName'], "未命名任务")


class TestActionExecution(unittest.TestCase):
    """动作执行功能测试"""

    def test_execute_wait_action(self):
        """测试等待动作执行"""
        with patch('ui_zero.cli.get_text') as mock_get_text:
            mock_get_text.side_effect = lambda key, *args: {
                "execute_wait_action_thought": f"执行等待动作: {args[0]}毫秒"
            }.get(key, f"mocked_{key}")
            
            result = execute_wait_action(1500, "test_task")

            self.assertIsInstance(result, ActionOutput)
            self.assertEqual(result.action, "wait")
            self.assertEqual(result.content, "1500")
            self.assertEqual(result.thought, "执行等待动作: 1500毫秒")

    def test_execute_wait_action_default_task_name(self):
        """测试等待动作执行（默认任务名）"""
        with patch('ui_zero.cli.get_text') as mock_get_text:
            mock_get_text.side_effect = lambda key, *args: {
                "execute_wait_action_thought": f"执行等待动作: {args[0]}毫秒"
            }.get(key, f"mocked_{key}")
            
            result = execute_wait_action(2000)

            self.assertEqual(result.action, "wait")
            self.assertEqual(result.content, "2000")
            self.assertEqual(result.thought, "执行等待动作: 2000毫秒")


class TestUnifiedActionExecution(unittest.TestCase):
    """统一动作执行功能测试"""

    def setUp(self):
        """测试前准备"""
        self.mock_adb = Mock()
        self.mock_agent = Mock(spec=AndroidAgent)
        self.mock_agent.adb = self.mock_adb

    def test_execute_unified_action_wait_cli_mode(self):
        """测试CLI模式下的等待动作执行"""
        action_dict = {
            "type": "wait",
            "duration": 1000,
            "taskName": "test_wait",
            "continueOnError": False
        }

        with patch('ui_zero.cli.get_text') as mock_get_text, \
             patch('ui_zero.cli.take_action') as mock_take_action:
            
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
                    return f"mocked_{key}_{args}"
            
            mock_get_text.side_effect = mock_get_text_func

            result = execute_unified_action(
                action_dict,
                self.mock_agent,
                )

            # 验证返回结果
            self.assertIsInstance(result, ActionOutput)
            self.assertEqual(result.action, "finished")
            self.assertIn("等待 1000ms 完成", result.content)

            # 验证调用
            mock_take_action.assert_called_once()
            self.assertEqual(len(mock_get_text.call_args_list), 3)  # 3个get_text调用

    def test_execute_unified_action_wait_gui_mode(self):
        """测试GUI模式下的等待动作执行"""
        action_dict = {
            "type": "wait",
            "duration": 500,
            "taskName": "test_wait",
            "continueOnError": False
        }

        mock_preaction_callback = Mock()
        mock_postaction_callback = Mock()

        with patch('ui_zero.cli.take_action') as mock_take_action:
            result = execute_unified_action(
                action_dict,
                self.mock_agent,
                preaction_callback=mock_preaction_callback,
                postaction_callback=mock_postaction_callback,
            )

            # 验证回调被调用
            mock_preaction_callback.assert_called_once()
            mock_postaction_callback.assert_called_once()

            # 验证take_action被调用
            mock_take_action.assert_called_once()

    def test_execute_unified_action_wait_default_duration(self):
        """测试等待动作的默认时长"""
        action_dict = {
            "type": "wait",
            "taskName": "test_wait"
            # 不指定duration
        }

        with patch('ui_zero.cli.take_action'), \
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
                    return f"mocked_{key}_{args}"
            
            mock_get_text.side_effect = mock_get_text_func

            result = execute_unified_action(
                action_dict,
                self.mock_agent,
                )

            self.assertEqual(result.action, "finished")
            self.assertIn("等待 2000ms 完成", result.content)  # 默认2000ms

    def test_execute_unified_action_ai_cli_mode(self):
        """测试CLI模式下的AI动作执行"""
        action_dict = {
            "type": "ai_action",
            "prompt": "test prompt",
            "taskName": "test_ai",
            "continueOnError": False
        }

        mock_result = Mock(spec=ActionOutput)
        self.mock_agent.run.return_value = mock_result

        result = execute_unified_action(
            action_dict,
            self.mock_agent,
            include_history=True,
            debug=False,
        )

        # 验证agent.run被正确调用
        self.mock_agent.run.assert_called_once_with(
            "test prompt",
            screenshot_callback=None,
            preaction_callback=None,
            postaction_callback=None,
            stream_resp_callback=None,
            include_history=True,
            debug=False,
            timeout=None
        )
        
        self.assertEqual(result, mock_result)

    def test_execute_unified_action_ai_with_timeout(self):
        """测试AI动作支持timeout参数"""
        action_dict = {
            "type": "ai_action",
            "prompt": "test prompt",
            "timeout": 5000,  # 5秒timeout
            "taskName": "test_ai",
            "continueOnError": False
        }

        mock_result = Mock(spec=ActionOutput)
        self.mock_agent.run.return_value = mock_result

        result = execute_unified_action(
            action_dict,
            self.mock_agent,
            include_history=True,
            debug=False,
        )

        # 验证agent.run被正确调用，包含timeout参数
        self.mock_agent.run.assert_called_once_with(
            "test prompt",
            screenshot_callback=None,
            preaction_callback=None,
            postaction_callback=None,
            stream_resp_callback=None,
            include_history=True,
            debug=False,
            timeout=5000
        )
        
        self.assertEqual(result, mock_result)

    def test_execute_unified_action_ai_gui_mode(self):
        """测试GUI模式下的AI动作执行"""
        action_dict = {
            "type": "ai_action",
            "prompt": "test prompt",
            "taskName": "test_ai",
            "continueOnError": False
        }

        mock_result = Mock(spec=ActionOutput)
        mock_screenshot_callback = Mock()
        mock_preaction_callback = Mock()
        mock_postaction_callback = Mock()
        mock_stream_callback = Mock()

        self.mock_agent.run.return_value = mock_result

        result = execute_unified_action(
            action_dict,
            self.mock_agent,
            screenshot_callback=mock_screenshot_callback,
            preaction_callback=mock_preaction_callback,
            postaction_callback=mock_postaction_callback,
            stream_resp_callback=mock_stream_callback,
        )

        # 验证agent.run被正确调用
        self.mock_agent.run.assert_called_once_with(
            "test prompt",
            screenshot_callback=mock_screenshot_callback,
            preaction_callback=mock_preaction_callback,
            postaction_callback=mock_postaction_callback,
            stream_resp_callback=mock_stream_callback,
            include_history=True,
            debug=False,
            timeout=None
        )

        self.assertEqual(result, mock_result)

    def test_execute_unified_action_unknown_type(self):
        """测试未知动作类型"""
        action_dict = {
            "type": "unknown_action",
            "taskName": "test_unknown"
        }

        with patch('ui_zero.cli.get_text') as mock_get_text:
            mock_get_text.side_effect = lambda key, *args: {
                "unsupported_action_type": f"不支持的动作类型: {args[0]}"
            }.get(key, f"mocked_{key}")

            result = execute_unified_action(
                action_dict,
                self.mock_agent,
                )

            self.assertEqual(result.action, "error")
            self.assertIn("不支持的动作类型", result.content)


class TestStepRunner(unittest.TestCase):
    """StepRunner类测试"""

    def setUp(self):
        """测试前准备"""
        self.mock_agent = Mock(spec=AndroidAgent)
        self.test_runner = StepRunner(self.mock_agent)

    def test_step_runner_init(self):
        """测试StepRunner初始化"""
        self.assertEqual(self.test_runner.agent, self.mock_agent)

    def test_run_step_success(self):
        """测试成功执行步骤"""
        mock_result = Mock(spec=ActionOutput)
        self.mock_agent.run.return_value = mock_result

        with patch('ui_zero.cli.get_text') as mock_get_text:
            mock_get_text.return_value = "test log message"

            result = self.test_runner.run_step("test step")

            self.assertEqual(result, mock_result)
            self.mock_agent.run.assert_called_once()

    def test_run_step_with_callbacks(self):
        """测试带回调的步骤执行"""
        mock_result = Mock(spec=ActionOutput)
        self.mock_agent.run.return_value = mock_result

        mock_screenshot_callback = Mock()
        mock_preaction_callback = Mock()
        mock_postaction_callback = Mock()
        mock_stream_callback = Mock()

        result = self.test_runner.run_step(
            "test step",
            screenshot_callback=mock_screenshot_callback,
            preaction_callback=mock_preaction_callback,
            postaction_callback=mock_postaction_callback,
            stream_resp_callback=mock_stream_callback
        )

        # 验证agent.run被调用且传递了正确参数
        self.mock_agent.run.assert_called_once_with(
            "test step",
            max_iters=10,
            screenshot_callback=mock_screenshot_callback,
            preaction_callback=mock_preaction_callback,
            postaction_callback=mock_postaction_callback,
            stream_resp_callback=mock_stream_callback,
            timeout=None
        )

    def test_run_step_exception(self):
        """测试步骤执行异常"""
        self.mock_agent.run.side_effect = Exception("test error")

        with patch('ui_zero.cli.get_text') as mock_get_text, \
             patch('ui_zero.cli.logger') as mock_logger:
            
            mock_get_text.side_effect = lambda key, *args: f"mocked_{key}"

            with self.assertRaises(Exception):
                self.test_runner.run_step("test step")

            mock_logger.error.assert_called_once()


class TestRunTestcases(unittest.TestCase):
    """run_testcases函数测试"""

    def setUp(self):
        """测试前准备"""
        self.mock_adb = Mock(spec=ADBTool)
        self.mock_adb.auto_selected_device = False
        self.mock_adb.device_id = "test_device"
        self.mock_agent = Mock(spec=AndroidAgent)

    @patch('ui_zero.cli.ADBTool')
    @patch('ui_zero.cli.AndroidAgent')
    @patch('ui_zero.cli.StepRunner')
    @patch('ui_zero.cli.execute_unified_action')
    def test_run_testcases_cli_mode(self, mock_execute_unified, mock_test_runner_class, 
                                   mock_agent_class, mock_adb_class):
        """测试CLI模式下的测试用例执行"""
        # 设置模拟对象
        mock_adb_class.return_value = self.mock_adb
        mock_agent_class.return_value = self.mock_agent

        mock_result = Mock(spec=ActionOutput)
        mock_result.is_finished.return_value = True
        mock_execute_unified.return_value = mock_result

        testcases = [
            {
                "type": "ai_action",
                "prompt": "test action 1",
                "taskName": "task1",
                "continueOnError": False
            },
            {
                "type": "wait",
                "duration": 1000,
                "taskName": "task2",
                "continueOnError": False
            }
        ]

        with patch('ui_zero.cli.get_text') as mock_get_text:
            mock_get_text.side_effect = lambda key, *args: f"mocked_{key}_{args}"

            run_testcases(
                testcases,
                include_history=True,
                debug=False,
                )

            # 验证execute_unified_action被调用了两次
            self.assertEqual(mock_execute_unified.call_count, 2)

            # 验证第一次调用参数
            first_call = mock_execute_unified.call_args_list[0]
            self.assertEqual(first_call[0][0], testcases[0])  # action_dict
            # Check that the agent was passed as the second argument
            self.assertEqual(first_call[0][1], self.mock_agent)

    @patch('ui_zero.cli.ADBTool')
    @patch('ui_zero.cli.AndroidAgent')
    @patch('ui_zero.cli.execute_unified_action')
    def test_run_testcases_continue_on_error(self, mock_execute_unified, 
                                           mock_agent_class, mock_adb_class):
        """测试continueOnError功能"""
        mock_adb_class.return_value = self.mock_adb
        mock_agent_class.return_value = self.mock_agent

        # 第一个动作抛出异常，但应该继续执行第二个
        mock_execute_unified.side_effect = [
            Exception("test error"),  # 第一个动作失败
            Mock(spec=ActionOutput, is_finished=lambda: True)  # 第二个动作成功
        ]

        testcases = [
            {
                "type": "ai_action",
                "prompt": "failing action",
                "taskName": "task1",
                "continueOnError": True  # 错误时继续
            },
            {
                "type": "ai_action",
                "prompt": "success action",
                "taskName": "task2",
                "continueOnError": False
            }
        ]

        with patch('ui_zero.cli.get_text') as mock_get_text:
            mock_get_text.side_effect = lambda key, *args: f"mocked_{key}_{args}"

            # 应该不抛出异常，继续执行第二个测试用例
            run_testcases(
                testcases,
                )

            # 验证两个动作都被尝试执行
            self.assertEqual(mock_execute_unified.call_count, 2)

    @patch('ui_zero.cli.ADBTool')
    @patch('ui_zero.cli.AndroidAgent')
    @patch('ui_zero.cli.execute_unified_action')
    def test_run_testcases_stop_on_error(self, mock_execute_unified, 
                                       mock_agent_class, mock_adb_class):
        """测试遇到错误时停止执行"""
        mock_adb_class.return_value = self.mock_adb
        mock_agent_class.return_value = self.mock_agent

        mock_execute_unified.side_effect = Exception("test error")

        testcases = [
            {
                "type": "ai_action",
                "prompt": "failing action",
                "taskName": "task1",
                "continueOnError": False  # 错误时停止
            },
            {
                "type": "ai_action",
                "prompt": "should not execute",
                "taskName": "task2",
                "continueOnError": False
            }
        ]

        with patch('ui_zero.cli.get_text') as mock_get_text:
            mock_get_text.side_effect = lambda key, *args: f"mocked_{key}_{args}"

            run_testcases(
                testcases,
                )

            # 只应该执行第一个动作
            self.assertEqual(mock_execute_unified.call_count, 1)

    @patch('ui_zero.cli.ADBTool')
    @patch('ui_zero.cli.AndroidAgent')
    @patch('ui_zero.cli.execute_unified_action')
    def test_run_testcases_not_finished_continue_on_error(self, mock_execute_unified, 
                                                         mock_agent_class, mock_adb_class):
        """测试任务未完成时的continueOnError逻辑"""
        mock_adb_class.return_value = self.mock_adb
        mock_agent_class.return_value = self.mock_agent

        # 第一个动作未完成，第二个动作成功
        mock_result_not_finished = Mock(spec=ActionOutput)
        mock_result_not_finished.is_finished.return_value = False
        mock_result_finished = Mock(spec=ActionOutput)
        mock_result_finished.is_finished.return_value = True
        
        mock_execute_unified.side_effect = [
            mock_result_not_finished,  # 第一个动作未完成
            mock_result_finished       # 第二个动作成功
        ]

        testcases = [
            {
                "type": "ai_action",
                "prompt": "not finishing action",
                "taskName": "task1",
                "continueOnError": True  # 错误时继续
            },
            {
                "type": "ai_action",
                "prompt": "finishing action",
                "taskName": "task2",
                "continueOnError": False
            }
        ]

        with patch('ui_zero.cli.get_text') as mock_get_text:
            mock_get_text.side_effect = lambda key, *args: f"mocked_{key}_{args}"

            run_testcases(
                testcases,
                )

            # 两个动作都应该被执行
            self.assertEqual(mock_execute_unified.call_count, 2)

    @patch('ui_zero.cli.ADBTool')
    @patch('ui_zero.cli.AndroidAgent')
    @patch('ui_zero.cli.execute_unified_action')
    def test_run_testcases_not_finished_stop_on_error(self, mock_execute_unified, 
                                                     mock_agent_class, mock_adb_class):
        """测试任务未完成且continueOnError=False时停止执行"""
        mock_adb_class.return_value = self.mock_adb
        mock_agent_class.return_value = self.mock_agent

        # 第一个动作未完成
        mock_result_not_finished = Mock(spec=ActionOutput)
        mock_result_not_finished.is_finished.return_value = False
        
        mock_execute_unified.return_value = mock_result_not_finished

        testcases = [
            {
                "type": "ai_action",
                "prompt": "not finishing action",
                "taskName": "task1",
                "continueOnError": False  # 错误时停止
            },
            {
                "type": "ai_action",
                "prompt": "should not execute",
                "taskName": "task2",
                "continueOnError": False
            }
        ]

        with patch('ui_zero.cli.get_text') as mock_get_text:
            mock_get_text.side_effect = lambda key, *args: f"mocked_{key}_{args}"

            run_testcases(
                testcases,
                )

            # 只应该执行第一个动作
            self.assertEqual(mock_execute_unified.call_count, 1)

    @patch('ui_zero.cli.ADBTool')
    @patch('ui_zero.cli.AndroidAgent')
    @patch('ui_zero.cli.execute_unified_action')
    def test_run_testcases_keyboard_interrupt(self, mock_execute_unified, 
                                            mock_agent_class, mock_adb_class):
        """测试键盘中断处理"""
        mock_adb_class.return_value = self.mock_adb
        mock_agent_class.return_value = self.mock_agent

        mock_execute_unified.side_effect = KeyboardInterrupt()

        testcases = [
            {
                "type": "ai_action",
                "prompt": "interrupted action",
                "taskName": "task1",
                "continueOnError": False
            }
        ]

        with patch('ui_zero.cli.get_text') as mock_get_text:
            mock_get_text.side_effect = lambda key, *args: f"mocked_{key}_{args}"

            with self.assertRaises(SystemExit):
                run_testcases(
                    testcases,
                        )


class TestExecuteSingleStep(unittest.TestCase):
    """execute_single_step函数测试"""

    @patch('ui_zero.cli.ADBTool')
    @patch('ui_zero.cli.AndroidAgent')
    @patch('ui_zero.cli.StepRunner')
    def test_execute_single_step_with_agent(self, mock_test_runner_class, 
                                          mock_agent_class, mock_adb_class):
        """测试使用提供的agent执行单步"""
        mock_agent = Mock(spec=AndroidAgent)
        mock_test_runner = Mock()
        mock_result = Mock(spec=ActionOutput)
        
        mock_test_runner_class.return_value = mock_test_runner
        mock_test_runner.run_step.return_value = mock_result

        result = execute_single_step(
            "test step",
            agent=mock_agent
        )

        self.assertEqual(result, mock_result)
        mock_test_runner_class.assert_called_once_with(mock_agent)
        mock_test_runner.run_step.assert_called_once()

    @patch('ui_zero.cli.ADBTool')
    @patch('ui_zero.cli.AndroidAgent')
    @patch('ui_zero.cli.StepRunner')
    def test_execute_single_step_without_agent(self, mock_test_runner_class, 
                                             mock_agent_class, mock_adb_class):
        """测试不提供agent时自动创建"""
        mock_adb = Mock(spec=ADBTool)
        mock_agent = Mock(spec=AndroidAgent)
        mock_test_runner = Mock()
        mock_result = Mock(spec=ActionOutput)
        
        mock_adb_class.return_value = mock_adb
        mock_agent_class.return_value = mock_agent
        mock_test_runner_class.return_value = mock_test_runner
        mock_test_runner.run_step.return_value = mock_result

        result = execute_single_step("test step")

        self.assertEqual(result, mock_result)
        mock_adb_class.assert_called_once()
        mock_agent_class.assert_called_once_with(adb=mock_adb)


class TestRunTestcasesForGui(unittest.TestCase):
    """run_testcases_for_gui函数测试"""

    @patch('ui_zero.cli.run_testcases')
    def test_run_testcases_for_gui(self, mock_run_testcases):
        """测试GUI模式测试用例执行"""
        testcases = [{"type": "ai_action", "prompt": "test"}]
        mock_screenshot_callback = Mock()
        mock_preaction_callback = Mock()
        mock_postaction_callback = Mock()
        mock_stream_callback = Mock()

        run_testcases_for_gui(
            testcases,
            screenshot_callback=mock_screenshot_callback,
            preaction_callback=mock_preaction_callback,
            postaction_callback=mock_postaction_callback,
            stream_resp_callback=mock_stream_callback,
            include_history=False,
            debug=True,
            device_id="test_device"
        )

        # 验证run_testcases被正确调用
        mock_run_testcases.assert_called_once_with(
            testcase_prompts=testcases,
            screenshot_callback=mock_screenshot_callback,
            preaction_callback=mock_preaction_callback,
            postaction_callback=mock_postaction_callback,
            stream_resp_callback=mock_stream_callback,
            include_history=False,
            debug=True,
            device_id="test_device"
        )


if __name__ == '__main__':
    unittest.main()