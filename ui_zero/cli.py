#!/usr/bin/env python3
"""
UI-Zero command line interface

用法示例:
    # 使用默认测试用例文件
    ui-zero

    # 指定测试用例文件
    ui-zero --testcase test_case.json

    # 指定单个测试命令
    ui-zero --command "找到[假日乐消消]app，并打开"

    # 指定多个测试命令
    ui-zero --command "找到app" --command "点击按钮"
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Union

import dotenv
import yaml

from .adb import ADBTool
from .agent import ActionOutput, AndroidAgent
from .env_config import ensure_env_config, setup_env_interactive, validate_env
from .localization import get_text

# 加载环境变量
dotenv.load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 禁用httpx的INFO日志
logging.getLogger("httpx").setLevel(logging.WARNING)


def list_available_devices() -> List[str]:
    """列出所有可用的Android设备"""
    try:
        adb_tool = ADBTool()
        devices = adb_tool.get_connected_devices()
        return devices
    except Exception as e:
        logger.error(get_text("device_list_error", e))
        return []


class TestRunner:
    """测试运行器，用于执行测试用例"""

    def __init__(self, agent: AndroidAgent):
        """
        初始化测试运行器

        Args:
            agent: AndroidAgent实例
        """
        self.agent = agent

    def run_step(
        self,
        step: str,
        screenshot_callback: Optional[Callable[[bytes], None]] = None,
        preaction_callback: Optional[Callable[[str, ActionOutput], None]] = None,
        postaction_callback: Optional[Callable[[str, ActionOutput], None]] = None,
        stream_resp_callback: Optional[Callable[[str, bool], None]] = None,
    ) -> ActionOutput:
        """
        执行单个测试步骤

        Args:
            step: 测试步骤描述
            screenshot_callback: 截图回调函数
            preaction_callback: 动作前回调函数
            postaction_callback: 动作后回调函数
            stream_resp_callback: 流式响应回调函数

        Returns:
            执行结果
        """
        logger.info(get_text("step_execution_log", step))

        try:
            # 执行步骤
            result = self.agent.run(
                step,
                max_iters=10,
                screenshot_callback=screenshot_callback,
                preaction_callback=preaction_callback,
                postaction_callback=postaction_callback,
                stream_resp_callback=stream_resp_callback,
            )

            return result
        except Exception as e:
            logger.error(get_text("step_execution_error", e))
            raise


def load_testcase_from_file(testcase_file: str) -> list:
    """从JSON文件加载测试用例"""
    try:
        with open(testcase_file, "r", encoding="utf-8") as f:
            testcases = json.load(f)
        if not isinstance(testcases, list):
            raise ValueError(get_text("testcase_format_error"))
        return testcases
    except FileNotFoundError:
        print(get_text("testcase_file_not_found", testcase_file))
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(get_text("testcase_file_json_error", testcase_file, e))
        sys.exit(1)
    except Exception as e:
        print(get_text("testcase_file_load_error", e))
        sys.exit(1)


def load_yaml_config(yaml_file: str) -> Dict[str, Any]:
    """从YAML文件加载配置"""
    try:
        with open(yaml_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        if not isinstance(config, dict):
            raise ValueError(get_text("yaml_config_format_error"))
        return config
    except FileNotFoundError:
        print(get_text("yaml_config_file_not_found", yaml_file))
        sys.exit(1)
    except yaml.YAMLError as e:
        print(get_text("yaml_config_file_parse_error", yaml_file, e))
        sys.exit(1)
    except Exception as e:
        print(get_text("yaml_config_file_load_error", e))
        sys.exit(1)


def convert_yaml_to_testcases(
    config: Dict[str, Any],
) -> tuple[List[Union[str, Dict[str, Any]]], Optional[str]]:
    """将YAML配置转换为测试用例列表"""
    testcases = []
    device_id = None

    # 提取设备ID
    if "android" in config and config["android"] and "deviceId" in config["android"]:
        device_id = config["android"]["deviceId"]

    # 处理任务列表
    if "tasks" not in config or not isinstance(config["tasks"], list):
        raise ValueError(get_text("yaml_config_missing_tasks"))

    for task in config["tasks"]:
        if not isinstance(task, dict) or "flow" not in task:
            continue

        # task_name = task.get("name", "未命名任务")
        # continue_on_error = task.get("continueOnError", False)

        # 处理flow中的每个动作
        for action in task["flow"]:
            if not isinstance(action, dict):
                continue

            # 处理AI动作
            if "ai" in action:
                testcases.append(action["ai"])
            elif "aiAction" in action:
                testcases.append(action["aiAction"])
            elif "aiWaitFor" in action:
                # 暂时将等待条件作为普通AI动作处理
                # timeout = action.get("timeout", 30000)
                wait_prompt = action["aiWaitFor"]
                testcases.append(f"等待条件满足: {wait_prompt}")
            elif "aiAssert" in action:
                # 将断言作为AI动作处理
                assert_prompt = action["aiAssert"]
                # error_msg = action.get("errorMessage", "断言失败")
                testcases.append(f"验证: {assert_prompt}")
            elif "sleep" in action:
                # 添加sleep动作到测试用例列表
                sleep_ms = action["sleep"]
                testcases.append({"type": "sleep", "duration": sleep_ms})

    return testcases, device_id


def run_testcases(
    testcase_prompts: List[Union[str, Dict[str, Any]]],
    screenshot_callback: Optional[Callable[[bytes], None]] = None,
    preaction_callback: Optional[Callable[[str, ActionOutput], None]] = None,
    postaction_callback: Optional[Callable[[str, ActionOutput], None]] = None,
    stream_resp_callback: Optional[Callable[[str, bool], None]] = None,
    include_history: bool = True,
    debug: bool = False,
    is_cli_mode: bool = False,
    device_id: Optional[str] = None,
) -> None:
    """
    统一的测试用例执行函数，支持CLI和GUI模式

    Args:
        testcase_prompts: 测试用例列表
        screenshot_callback: 截图回调函数（GUI模式）
        preaction_callback: 动作前回调函数（GUI模式）
        postaction_callback: 动作后回调函数（GUI模式）
        stream_resp_callback: 流式响应回调函数
        include_history: 是否包含历史记录
        debug: 是否启用调试模式
        is_cli_mode: 是否为CLI模式
        device_id: 指定的设备ID
    """
    adb_tool = ADBTool(device_id=device_id) if device_id else ADBTool()
    agent = AndroidAgent(adb=adb_tool)
    test_runner = TestRunner(agent)

    # CLI模式的初始化输出
    if is_cli_mode:
        print(get_text("starting_test_execution"), len(testcase_prompts))
        if device_id:
            print(get_text("using_specified_device"), device_id)
        elif adb_tool.auto_selected_device:
            print(get_text("multiple_devices_auto_selected").format(adb_tool.device_id))
            print(get_text("recommend_specify_device"))
            print(get_text("using_auto_selected_device").format(adb_tool.device_id))
        else:
            print(get_text("using_default_device"))
        if debug:
            debug_history_key = (
                "debug_history_enabled" if include_history else "debug_history_disabled"
            )
            print(get_text(debug_history_key))
            debug_mode_key = "debug_mode_enabled" if debug else "debug_mode_disabled"
            print(get_text(debug_mode_key))

        # CLI模式的流式响应回调
        if stream_resp_callback is None:

            def default_stream_callback(text: str, finished: bool) -> None:
                if finished:
                    print("\n", flush=True)
                else:
                    print(f"{text}", end="", flush=True)

            stream_resp_callback = default_stream_callback

    prompt_idx = 0
    total_steps = len(testcase_prompts)

    while prompt_idx < total_steps:
        try:
            cur_action = testcase_prompts[prompt_idx]

            # 处理sleep动作
            if isinstance(cur_action, dict) and cur_action.get("type") == "sleep":
                duration_ms = cur_action.get("duration", 1000)
                duration_seconds = duration_ms / 1000.0

                if is_cli_mode:
                    print(
                        get_text("starting_sleep_action", prompt_idx + 1, duration_ms)
                    )

                time.sleep(duration_seconds)

                if is_cli_mode:
                    print(get_text("sleep_action_completed", prompt_idx + 1))

                prompt_idx += 1
                continue

            # 处理AI动作
            cur_action_prompt = str(cur_action)

            # CLI模式输出任务开始信息
            if is_cli_mode:
                print(get_text("starting_task", prompt_idx + 1, cur_action_prompt))

            # 根据模式选择执行方法
            if is_cli_mode:
                # CLI模式：直接使用agent.run，保持原有CLI行为
                result = agent.run(
                    cur_action_prompt,
                    stream_resp_callback=stream_resp_callback,
                    include_history=include_history,
                    debug=debug,
                )
            else:
                # GUI模式：使用test_runner.run_step，支持更多回调
                result = test_runner.run_step(
                    cur_action_prompt,
                    screenshot_callback=screenshot_callback,
                    preaction_callback=preaction_callback,
                    postaction_callback=postaction_callback,
                    stream_resp_callback=stream_resp_callback,
                )

            # 检查执行结果
            if result.is_finished():
                if is_cli_mode:
                    print(get_text("task_completed", prompt_idx + 1))
                prompt_idx += 1
            else:
                if is_cli_mode:
                    print(get_text("task_not_completed", prompt_idx + 1))
                    prompt_idx += 1
                else:
                    logger.warning(f"步骤 {prompt_idx + 1} 未完成")
                    prompt_idx += 1

        except KeyboardInterrupt:
            if is_cli_mode:
                print(get_text("user_interrupted"))
                sys.exit(0)
            else:
                logger.info("用户中断执行")
                raise
        except Exception as e:
            error_msg = f"执行步骤 {prompt_idx + 1} 时出错: {e}"
            if is_cli_mode:
                print(get_text("execution_error", e))
                break
            else:
                logger.error(error_msg)
                raise

    # CLI模式的完成输出
    if is_cli_mode:
        print(get_text("all_tasks_completed"))


def execute_single_step(
    step: str,
    agent: Optional[AndroidAgent] = None,
    screenshot_callback: Optional[Callable[[bytes], None]] = None,
    preaction_callback: Optional[Callable[[str, ActionOutput], None]] = None,
    postaction_callback: Optional[Callable[[str, ActionOutput], None]] = None,
    stream_resp_callback: Optional[Callable[[str, bool], None]] = None,
    device_id: Optional[str] = None,
) -> ActionOutput:
    """执行单个测试步骤（用于GUI模式）"""
    if agent is None:
        adb_tool = ADBTool(device_id=device_id) if device_id else ADBTool()
        agent = AndroidAgent(adb=adb_tool)

    test_runner = TestRunner(agent)
    return test_runner.run_step(
        step,
        screenshot_callback=screenshot_callback,
        preaction_callback=preaction_callback,
        postaction_callback=postaction_callback,
        stream_resp_callback=stream_resp_callback,
    )


def run_testcases_for_gui(
    testcase_prompts: List[Union[str, Dict[str, Any]]],
    screenshot_callback: Optional[Callable[[bytes], None]] = None,
    preaction_callback: Optional[Callable[[str, ActionOutput], None]] = None,
    postaction_callback: Optional[Callable[[str, ActionOutput], None]] = None,
    stream_resp_callback: Optional[Callable[[str, bool], None]] = None,
    include_history: bool = True,
    debug: bool = False,
    device_id: Optional[str] = None,
) -> None:
    """
    为GUI模式提供的批量执行函数，使用统一的执行逻辑
    这个函数直接调用统一的run_testcases函数，确保行为一致性
    """
    return run_testcases(
        testcase_prompts=testcase_prompts,
        screenshot_callback=screenshot_callback,
        preaction_callback=preaction_callback,
        postaction_callback=postaction_callback,
        stream_resp_callback=stream_resp_callback,
        include_history=include_history,
        debug=debug,
        is_cli_mode=False,
        device_id=device_id,
    )


def main() -> None:
    """主函数"""
    parser = argparse.ArgumentParser(
        description=get_text("cli_description"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=get_text("usage_examples"),
    )

    # 互斥参数组：要么使用testcase文件，要么使用command参数
    group = parser.add_mutually_exclusive_group()

    group.add_argument("--testcase", "-t", type=str, help=get_text("arg_testcase_help"))

    group.add_argument(
        "--command", "-c", action="append", help=get_text("arg_command_help")
    )

    parser.add_argument("--version", "-v", action="version", version="UI-Zero v0.1.4")

    parser.add_argument(
        "--no-history", action="store_true", help=get_text("arg_no_history_help")
    )

    parser.add_argument(
        "--debug", "-d", action="store_true", help=get_text("arg_debug_help")
    )

    parser.add_argument("--device", "-D", type=str, help=get_text("arg_device_help"))

    parser.add_argument(
        "--list-devices", action="store_true", help=get_text("arg_list_devices_help")
    )

    parser.add_argument(
        "--setup-env", action="store_true", help=get_text("arg_setup_env_help")
    )

    parser.add_argument(
        "--validate-env", action="store_true", help=get_text("arg_validate_env_help")
    )

    args = parser.parse_args()

    # 处理环境配置命令
    if args.setup_env:
        success = setup_env_interactive()
        sys.exit(0 if success else 1)

    if args.validate_env:
        success = validate_env()
        sys.exit(0 if success else 1)

    # 处理列出设备命令
    if args.list_devices:
        devices = list_available_devices()
        if devices:
            print(get_text("available_devices"))
            for device in devices:
                print(f"  - {device}")
        else:
            print(get_text("no_devices_found"))
        sys.exit(0)

    # 在执行主要功能前检查环境配置
    print(get_text("checking_env_config"))
    if not ensure_env_config(skip_interactive=True):
        print(get_text("env_config_incomplete_invalid"))
        success = setup_env_interactive()
        sys.exit(0 if success else 1)

    # 确定测试用例来源
    device_id_from_config = None
    if args.command:
        # 使用命令行指定的命令
        testcase_prompts = args.command
        print(get_text("using_cli_commands", len(testcase_prompts)))
    elif args.testcase:
        # 使用指定的测试用例文件
        if args.testcase.endswith((".yaml", ".yml")):
            # YAML配置文件
            config = load_yaml_config(args.testcase)
            testcase_prompts, device_id_from_config = convert_yaml_to_testcases(config)
            print(
                get_text("loaded_from_yaml_file", len(testcase_prompts), args.testcase)
            )
        else:
            # JSON测试用例文件
            testcase_prompts = load_testcase_from_file(args.testcase)
            print(get_text("loaded_from_file", args.testcase, len(testcase_prompts)))
    else:
        # 尝试使用默认文件（优先YAML）
        default_yaml_file = "test_case.yaml"
        default_json_file = "test_case.json"

        if os.path.exists(default_yaml_file):
            config = load_yaml_config(default_yaml_file)
            testcase_prompts, device_id_from_config = convert_yaml_to_testcases(config)
            print(
                get_text(
                    "loaded_from_yaml_file", len(testcase_prompts), default_yaml_file
                )
            )
        elif os.path.exists(default_json_file):
            testcase_prompts = load_testcase_from_file(default_json_file)
            print(
                get_text(
                    "loaded_from_default", default_json_file, len(testcase_prompts)
                )
            )
        else:
            # 没有找到可用的测试用例
            print(get_text("no_testcase_found", default_json_file))
            print(get_text("testcase_options"))
            print(get_text("use_help"))
            sys.exit(1)

    # 执行测试用例
    include_history = (
        not args.no_history
    )  # --no-history 为 True 时，include_history 为 False

    # 设备ID优先级：命令行参数 > YAML配置 > 自动选择
    final_device_id = args.device or device_id_from_config
    run_testcases(
        testcase_prompts,
        include_history=include_history,
        debug=args.debug,
        is_cli_mode=True,
        device_id=final_device_id,
    )


if __name__ == "__main__":
    main()
