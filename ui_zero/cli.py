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
from typing import Any, Callable, Dict, List, Optional

import dotenv
import yaml

from .adb import ADBTool
from .agent import ActionOutput, AndroidAgent, take_action
from .env_config import ensure_env_config, setup_env_interactive, validate_env
from .localization import get_text
from .logging_config import configure_logging, get_logger
from .ui_display import initialize_ui_display, get_ui_display, show_ai_response

# 加载环境变量
dotenv.load_dotenv()

# 延迟初始化logger，在main函数中根据模式配置
logger = None


def list_available_devices() -> List[str]:
    """列出所有可用的Android设备"""
    try:
        adb_tool = ADBTool()
        devices = adb_tool.get_connected_devices()
        return devices
    except Exception as e:
        # 使用统一的UI显示系统
        if logger is not None:
            logger.error(get_text("device_list_error", e))
        
        # 同时显示到UI界面
        from .ui_display import show_message
        show_message(get_text("device_list_error", str(e)), "error")
        return []


class StepRunner:
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
        postaction_callback: Optional[Callable[[str, ActionOutput, int], None]] = None,
        stream_resp_callback: Optional[Callable[[str, bool], None]] = None,
        timeout: Optional[int] = None,
    ) -> ActionOutput:
        """
        执行单个测试步骤

        Args:
            step: 测试步骤描述
            screenshot_callback: 截图回调函数
            preaction_callback: 动作前回调函数
            postaction_callback: 动作后回调函数
            stream_resp_callback: 流式响应回调函数
            timeout: 超时时间（毫秒）

        Returns:
            执行结果
        """
        if logger is not None:
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
                timeout=timeout,
            )

            return result
        except Exception as e:
            if logger is not None:
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
        if logger is not None:
            logger.error(get_text("testcase_file_not_found", testcase_file))
        sys.exit(1)
    except json.JSONDecodeError as e:
        if logger is not None:
            logger.error(get_text("testcase_file_json_error", testcase_file, e))
        sys.exit(1)
    except Exception as e:
        if logger is not None:
            logger.error(get_text("testcase_file_load_error", e))
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
        if logger is not None:
            logger.error(get_text("yaml_config_file_not_found", yaml_file))
        sys.exit(1)
    except yaml.YAMLError as e:
        if logger is not None:
            logger.error(get_text("yaml_config_file_parse_error", yaml_file, e))
        sys.exit(1)
    except Exception as e:
        if logger is not None:
            logger.error(get_text("yaml_config_file_load_error", e))
        sys.exit(1)


def convert_yaml_to_testcases(
    config: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], Optional[str]]:
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

        task_name = task.get("name", get_text("unnamed_task"))
        continue_on_error = task.get("continueOnError", False)

        # 处理flow中的每个动作
        for action in task["flow"]:
            if not isinstance(action, dict):
                continue
            action_continue_on_error = action.get("continueOnError", continue_on_error)
            # 处理AI动作
            if "ai" in action:
                testcase = {
                    "type": "ai_action",
                    "prompt": action["ai"],
                    "continueOnError": action_continue_on_error,
                    "taskName": task_name,
                }
                # 添加timeout参数支持
                if "timeout" in action:
                    testcase["timeout"] = action["timeout"]
                testcases.append(testcase)
            elif "aiAction" in action:
                testcase = {
                    "type": "ai_action",
                    "prompt": action["aiAction"],
                    "continueOnError": action_continue_on_error,
                    "taskName": task_name,
                }
                # 添加timeout参数支持
                if "timeout" in action:
                    testcase["timeout"] = action["timeout"]
                testcases.append(testcase)
            elif "aiWaitFor" in action:
                # 将等待条件作为AI动作处理，支持timeout参数
                wait_prompt = action["aiWaitFor"]
                testcase = {
                    "type": "ai_action",
                    "prompt": get_text("ai_wait_for_condition", wait_prompt),
                    "continueOnError": action_continue_on_error,
                    "taskName": task_name,
                }
                # 添加timeout参数支持
                if "timeout" in action:
                    testcase["timeout"] = action["timeout"]
                testcases.append(testcase)
            elif "aiAssert" in action:
                # 将断言作为AI动作处理，支持errorMessage参数
                assert_prompt = action["aiAssert"]
                error_msg = action.get("errorMessage", "")
                testcases.append(
                    {
                        "type": "ai_assert",
                        "prompt": assert_prompt,
                        "errorMessage": error_msg,
                        "continueOnError": action_continue_on_error,
                        "taskName": task_name,
                    }
                )
            elif "sleep" in action:
                # 将sleep动作转换为wait动作（向后兼容）
                wait_ms = action["sleep"]
                testcases.append(
                    {
                        "type": "wait",
                        "duration": wait_ms,
                        "continueOnError": action_continue_on_error,
                        "taskName": task_name,
                    }
                )
            elif "wait" in action:
                # 添加wait动作到测试用例列表
                wait_ms = action["wait"]
                testcases.append(
                    {
                        "type": "wait",
                        "duration": wait_ms,
                        "continueOnError": action_continue_on_error,
                        "taskName": task_name,
                    }
                )

    return testcases, device_id


def execute_wait_action(
    duration_ms: int, task_name: str = ""
) -> ActionOutput:  # pylint: disable=unused-argument
    """
    执行等待动作，返回ActionOutput对象

    Args:
        duration_ms: 等待时间（毫秒）
        task_name: 任务名称

    Returns:
        ActionOutput对象，表示等待动作已完成
    """
    return ActionOutput(
        thought=get_text("execute_wait_action_thought", duration_ms),
        action="wait",
        content=str(duration_ms),
    )


def execute_unified_action(
    action_dict: Dict[str, Any],
    agent: AndroidAgent,
    screenshot_callback: Optional[Callable[[bytes], None]] = None,
    preaction_callback: Optional[Callable[[str, ActionOutput], None]] = None,
    postaction_callback: Optional[Callable[[str, ActionOutput, int], None]] = None,
    stream_resp_callback: Optional[Callable[[str, bool], None]] = None,
    include_history: bool = True,
    debug: bool = False,
) -> ActionOutput:
    """
    统一的动作执行函数，支持AI动作和直接指令（如睡眠）

    Args:
        action_dict: 动作字典，包含type、prompt等信息
        agent: AndroidAgent实例
        其他参数同run_testcases

    Returns:
        ActionOutput对象
    """
    action_type = action_dict.get("type", "ai_action")
    task_name = action_dict.get("taskName", "")

    if action_type == "wait":
        # 处理等待动作
        duration_ms = action_dict.get("duration", 2000)  # 默认2秒

        if logger is not None:
            logger.info(get_text("starting_wait_action", task_name, duration_ms))

        # 创建等待动作的ActionOutput
        wait_output = execute_wait_action(duration_ms, task_name)

        # 执行动作前回调
        if preaction_callback:
            preaction_callback(
                get_text("wait_callback_description", duration_ms), wait_output
            )

        # 执行等待动作
        take_action(agent.adb, wait_output)

        # 执行动作后回调
        if postaction_callback:
            postaction_callback(
                get_text("wait_callback_description", duration_ms), wait_output, 0
            )

        if logger is not None:
            logger.info(get_text("wait_action_completed", task_name))

        # 等待动作总是成功完成
        return ActionOutput(
            thought=get_text("wait_action_thought_completed", duration_ms),
            action="finished",
            content=get_text("wait_action_content_completed", duration_ms),
        )
    elif action_type == "ai_assert":
        # 处理AI断言动作
        prompt = action_dict.get("prompt", "")
        error_message = action_dict.get("errorMessage", "")
        continue_on_error = action_dict.get("continueOnError", False)

        if logger is not None:
            logger.info(get_text("starting_assert_action", task_name, prompt))

        # 调用agent.run，要求模型判断prompt中描述的情况是否为真
        assert_prompt = get_text("ai_assert_prompt", prompt)

        # 执行断言检查
        result = agent.run(
            assert_prompt,
            max_iters=1,  # 断言只需要一次判断
            screenshot_callback=screenshot_callback,
            preaction_callback=preaction_callback,
            postaction_callback=postaction_callback,
            stream_resp_callback=stream_resp_callback,
            debug=debug,
        )

        # 检查断言结果
        is_assert_true = (
            result.action == "finished"
            and result.content
            and "Assert is true" in result.content
        )

        if is_assert_true:
            # 断言为真，继续执行
            if logger is not None:
                logger.info(get_text("assert_passed", task_name))
            return ActionOutput(
                thought=get_text("assert_true_thought", prompt),
                action="finished",
                content=get_text("assert_true_content"),
            )

        # 断言为假
        if logger is not None:
            logger.warning(get_text("assert_failed", task_name))

        # 根据continueOnError决定是否抛出异常
        if continue_on_error:
            if not error_message:
                error_description = get_text("assert_false_thought_continue", prompt)
            else:
                error_description = get_text(
                    "assert_false_thought_continue_with_msg", prompt, error_message
                )

            if logger is not None:
                logger.warning(error_description)

            return ActionOutput(
                thought=error_description,
                action="finished",
                content=get_text("assert_false_content"),
            )

        # 抛出异常中断执行，使用自定义错误消息或默认消息
        if error_message:
            raise RuntimeError(get_text("assert_failed_error", error_message))

        raise RuntimeError(get_text("assert_failed_error", prompt))

    elif action_type == "ai_action":
        # 处理AI动作
        prompt = action_dict.get("prompt", "")
        timeout = action_dict.get("timeout")  # 获取timeout参数

        # 统一使用agent.run，不再区分CLI和GUI模式
        return agent.run(
            prompt,
            screenshot_callback=screenshot_callback,
            preaction_callback=preaction_callback,
            postaction_callback=postaction_callback,
            stream_resp_callback=stream_resp_callback,
            include_history=include_history,
            debug=debug,
            timeout=timeout,
        )

    else:
        # 未知动作类型
        error_msg = get_text("unsupported_action_type", action_type)
        return ActionOutput(thought=error_msg, action="error", content=error_msg)


def run_testcases(
    testcase_prompts: List[Dict[str, Any]],
    screenshot_callback: Optional[Callable[[bytes], None]] = None,
    preaction_callback: Optional[Callable[[str, ActionOutput], None]] = None,
    postaction_callback: Optional[Callable[[str, ActionOutput, int], None]] = None,
    stream_resp_callback: Optional[Callable[[str, bool], None]] = None,
    include_history: bool = True,
    debug: bool = False,
    device_id: Optional[str] = None,
) -> None:
    """
    统一的测试用例执行函数

    Args:
        testcase_prompts: 测试用例列表
        screenshot_callback: 截图回调函数
        preaction_callback: 动作前回调函数
        postaction_callback: 动作后回调函数
        stream_resp_callback: 流式响应回调函数
        include_history: 是否包含历史记录
        debug: 是否启用调试模式
        device_id: 指定的设备ID
    """
    adb_tool = ADBTool(device_id=device_id) if device_id else ADBTool()
    agent = AndroidAgent(adb=adb_tool)
    _ = StepRunner(agent)  # Create runner for any initialization side effects

    # 获取UI显示系统
    ui_display = get_ui_display()
    
    # 准备任务描述列表
    task_descriptions = []
    for i, action in enumerate(testcase_prompts):
        action_type = action.get("type", "ai_action")
        if action_type == "ai_action":
            desc = action.get("prompt", f"任务 {i+1}")
            # 限制描述长度
            if len(desc) > 50:
                desc = desc[:47] + "..."
            task_descriptions.append(desc)
        elif action_type == "wait":
            duration = action.get("duration", 2000)
            task_descriptions.append(f"等待 {duration}ms")
        elif action_type == "ai_assert":
            prompt = action.get("prompt", "")
            desc = f"断言: {prompt}"
            if len(desc) > 50:
                desc = desc[:47] + "..."
            task_descriptions.append(desc)
        else:
            task_descriptions.append(f"未知任务类型: {action_type}")
    
    # 初始化进度显示
    if ui_display:
        ui_display.initialize_progress(len(testcase_prompts), task_descriptions)
        ui_display.start_display()
    
    # 输出初始化信息到日志
    if logger is not None:
        logger.info(f"{get_text('starting_test_execution')} {len(testcase_prompts)}")
        if device_id:
            logger.info(f"{get_text('using_specified_device')} {device_id}")
        elif adb_tool.auto_selected_device:
            logger.info(
                get_text("multiple_devices_auto_selected").format(adb_tool.device_id)
            )
            logger.info(get_text("recommend_specify_device"))
            logger.info(
                get_text("using_auto_selected_device").format(adb_tool.device_id)
            )
        else:
            logger.info(get_text("using_default_device"))
        if debug:
            debug_history_key = (
                "debug_history_enabled" if include_history else "debug_history_disabled"
            )
            logger.debug(get_text(debug_history_key))
            debug_mode_key = "debug_mode_enabled" if debug else "debug_mode_disabled"
            logger.debug(get_text(debug_mode_key))

    # 设置默认流式响应回调（使用UI显示系统）
    if stream_resp_callback is None:
        stream_resp_callback = show_ai_response

    # 创建postaction回调来更新剩余迭代次数
    def update_iterations_callback(prompt: str, output: ActionOutput, left_iters: int):
        """更新UI显示中的剩余迭代次数"""
        if ui_display:
            ui_display.update_current_step(prompt_idx, task_descriptions[prompt_idx], "running", left_iters)
    
    # 如果没有提供postaction_callback，使用我们的默认回调
    if postaction_callback is None:
        postaction_callback = update_iterations_callback

    prompt_idx = 0
    total_steps = len(testcase_prompts)
    execution_success = True

    try:
        while prompt_idx < total_steps:
            cur_action = None
            try:
                cur_action = testcase_prompts[prompt_idx]

                # 提取动作信息
                action_type = cur_action.get("type", "ai_action")
                continue_on_error = cur_action.get("continueOnError", False)
                _ = cur_action.get("taskName", get_text("step_number", prompt_idx + 1))
                
                # 更新UI进度显示
                if ui_display:
                    ui_display.update_current_step(prompt_idx, task_descriptions[prompt_idx], "running")

                # AI动作需要特殊的提示输出
                if action_type == "ai_action":
                    cur_action_prompt = cur_action["prompt"]
                    if logger is not None:
                        logger.info(
                            get_text("starting_task", prompt_idx + 1, cur_action_prompt)
                        )

                # 执行动作
                result = execute_unified_action(
                    cur_action,
                    agent,
                    screenshot_callback=screenshot_callback,
                    preaction_callback=preaction_callback,
                    postaction_callback=postaction_callback,
                    stream_resp_callback=stream_resp_callback,
                    include_history=include_history,
                    debug=debug,
                )

                # 检查执行结果
                if result.is_finished():
                    if logger is not None:
                        logger.info(get_text("task_completed", prompt_idx + 1))
                    
                    # 标记步骤完成
                    if ui_display:
                        ui_display.complete_step(prompt_idx)
                    
                    prompt_idx += 1
                else:
                    # 任务未完成，根据continueOnError决定是否继续
                    if continue_on_error:
                        if logger is not None:
                            logger.warning(
                                get_text("step_not_completed_warning", prompt_idx + 1)
                            )
                            logger.info(get_text("continue_on_error_message"))
                        
                        # 标记为警告状态
                        if ui_display:
                            ui_display.update_current_step(prompt_idx, task_descriptions[prompt_idx], "warning")
                        
                        prompt_idx += 1
                    else:
                        # 不允许继续，停止执行
                        if logger is not None:
                            logger.error(get_text("task_not_completed", prompt_idx + 1))
                            logger.error(get_text("task_failed_stopping_execution"))
                        
                        # 标记为错误状态
                        if ui_display:
                            ui_display.update_current_step(prompt_idx, task_descriptions[prompt_idx], "error")
                        
                        execution_success = False
                        break

            except KeyboardInterrupt:
                if logger is not None:
                    logger.info(get_text("user_interrupted_execution"))
                
                # 更新UI显示中断状态
                if ui_display:
                    ui_display.show_message(get_text("user_interrupted_execution"), "warning")
                    ui_display.finalize(False)
                    ui_display.close()
                
                sys.exit(0)
            except Exception as e:
                # 检查是否应该继续执行
                should_continue = (
                    cur_action.get("continueOnError", False) if cur_action else False
                )

                if should_continue:
                    if logger is not None:
                        logger.error(get_text("execution_error", e))
                        logger.info(get_text("continue_on_error_message"))
                    
                    # 标记为警告状态但继续
                    if ui_display:
                        ui_display.update_current_step(prompt_idx, task_descriptions[prompt_idx], "warning")
                    
                    prompt_idx += 1
                else:
                    if logger is not None:
                        logger.error(get_text("execution_error", e))
                    
                    # 标记为错误状态
                    if ui_display:
                        ui_display.update_current_step(prompt_idx, task_descriptions[prompt_idx], "error")
                    
                    execution_success = False
                    break

        # 完成输出
        if logger is not None:
            logger.info(get_text("all_tasks_completed"))
            
    finally:
        # 最终化UI显示
        if ui_display:
            ui_display.finalize(execution_success)
            ui_display.close()


def execute_single_step(
    step: str,
    agent: Optional[AndroidAgent] = None,
    screenshot_callback: Optional[Callable[[bytes], None]] = None,
    preaction_callback: Optional[Callable[[str, ActionOutput], None]] = None,
    postaction_callback: Optional[Callable[[str, ActionOutput, int], None]] = None,
    stream_resp_callback: Optional[Callable[[str, bool], None]] = None,
    device_id: Optional[str] = None,
    timeout: Optional[int] = None,
) -> ActionOutput:
    """执行单个测试步骤（用于GUI模式）"""
    if agent is None:
        adb_tool = ADBTool(device_id=device_id) if device_id else ADBTool()
        agent = AndroidAgent(adb=adb_tool)

    test_runner = StepRunner(agent)
    return test_runner.run_step(
        step,
        screenshot_callback=screenshot_callback,
        preaction_callback=preaction_callback,
        postaction_callback=postaction_callback,
        stream_resp_callback=stream_resp_callback,
        timeout=timeout,
    )


def run_testcases_for_gui(
    testcase_prompts: List[Dict[str, Any]],
    screenshot_callback: Optional[Callable[[bytes], None]] = None,
    preaction_callback: Optional[Callable[[str, ActionOutput], None]] = None,
    postaction_callback: Optional[Callable[[str, ActionOutput, int], None]] = None,
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

    parser.add_argument("--version", "-v", action="version", version="UI-Zero v0.1.9")

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

    parser.add_argument(
        "--serve", action="store_true", help=get_text("arg_serve_help")
    )

    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help=get_text("arg_host_help")
    )

    parser.add_argument(
        "--port", type=int, default=8000, help=get_text("arg_port_help")
    )


    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help=get_text("arg_log_level_help"),
    )

    parser.add_argument(
        "--output", "-o", type=str, help=get_text("arg_output_help")
    )

    args = parser.parse_args()

    # 配置文件日志系统
    log_level = getattr(logging, args.log_level.upper())
    configure_logging(level=log_level)
    
    # 初始化UI显示系统 - 服务器模式下禁用终端UI
    is_terminal_mode = not args.serve
    ui_display = initialize_ui_display(is_terminal=is_terminal_mode)

    # 获取配置好的logger
    global logger
    logger = get_logger("cli")

    # 处理环境配置命令
    if args.setup_env:
        success = setup_env_interactive()
        sys.exit(0 if success else 1)

    if args.validate_env:
        success = validate_env()
        sys.exit(0 if success else 1)

    # 处理启动服务器命令
    if args.serve:
        from .server import start_server
        logger.info(get_text("starting_api_server", args.host, args.port))
        success = start_server(host=args.host, port=args.port, log_level=args.log_level.lower())
        sys.exit(0 if success else 1)

    # 处理列出设备命令
    if args.list_devices:
        devices = list_available_devices()
        if devices:
            logger.info(get_text("available_devices"))
            for device in devices:
                logger.info(f"  - {device}")
        else:
            logger.info(get_text("no_devices_found"))
        sys.exit(0)

    # 在执行主要功能前检查环境配置
    logger.info(get_text("checking_env_config"))
    if not ensure_env_config(skip_interactive=True):
        logger.error(get_text("env_config_incomplete_invalid"))
        success = setup_env_interactive()
        sys.exit(0 if success else 1)

    # 确定测试用例来源
    device_id_from_config = None
    if args.command:
        # 使用命令行指定的命令，转换为统一格式
        testcase_prompts = [
            {
                "type": "ai_action",
                "prompt": cmd,
                "continueOnError": False,
                "taskName": get_text("command_number", i + 1),
                # 命令行模式默认不设置timeout，使用系统默认值
            }
            for i, cmd in enumerate(args.command)
        ]
        logger.info(get_text("using_cli_commands", len(testcase_prompts)))
    elif args.testcase:
        # 使用指定的测试用例文件
        if args.testcase.endswith((".yaml", ".yml")):
            # YAML配置文件
            config = load_yaml_config(args.testcase)
            testcase_prompts, device_id_from_config = convert_yaml_to_testcases(config)
            logger.info(
                get_text("loaded_from_yaml_file", len(testcase_prompts), args.testcase)
            )
        else:
            # JSON测试用例文件，转换为统一格式
            json_testcases = load_testcase_from_file(args.testcase)
            testcase_prompts = [
                {
                    "type": "ai_action",
                    "prompt": tc,
                    "continueOnError": False,
                    "taskName": get_text("step_number", i + 1),
                    # JSON格式暂不支持timeout参数，使用系统默认值
                }
                for i, tc in enumerate(json_testcases)
            ]
            logger.info(
                get_text("loaded_from_file", args.testcase, len(testcase_prompts))
            )
    else:
        # 尝试使用默认文件（优先YAML）
        default_yaml_file = "test_case.yaml"
        default_json_file = "test_case.json"

        if os.path.exists(default_yaml_file):
            config = load_yaml_config(default_yaml_file)
            testcase_prompts, device_id_from_config = convert_yaml_to_testcases(config)
            logger.info(
                get_text(
                    "loaded_from_yaml_file", len(testcase_prompts), default_yaml_file
                )
            )
        elif os.path.exists(default_json_file):
            json_testcases = load_testcase_from_file(default_json_file)
            testcase_prompts = [
                {
                    "type": "ai_action",
                    "prompt": tc,
                    "continueOnError": False,
                    "taskName": get_text("step_number", i + 1),
                    # 默认JSON文件暂不支持timeout参数，使用系统默认值
                }
                for i, tc in enumerate(json_testcases)
            ]
            logger.info(
                get_text(
                    "loaded_from_default", default_json_file, len(testcase_prompts)
                )
            )
        else:
            # 没有找到可用的测试用例
            logger.error(get_text("no_testcase_found", default_json_file))
            logger.error(get_text("testcase_options"))
            logger.error(get_text("use_help"))
            sys.exit(1)

    # 执行测试用例
    include_history = (
        not args.no_history
    )  # --no-history 为 True 时，include_history 为 False

    # 设备ID优先级：命令行参数 > YAML配置 > 自动选择
    final_device_id = args.device or device_id_from_config
    
    try:
        run_testcases(
            testcase_prompts,
            include_history=include_history,
            debug=args.debug,
            device_id=final_device_id,
        )
        
        # 执行完成后，如果指定了输出文件，导出结果
        if args.output:
            from .ui_display import export_execution_results_to_json
            if export_execution_results_to_json(args.output):
                logger.info(get_text("json_export_success", args.output))
            else:
                logger.error(get_text("json_export_failed", args.output))
                
    except KeyboardInterrupt:
        # 主函数级别的中断处理
        ui_display = get_ui_display()
        if ui_display:
            ui_display.close()
        sys.exit(0)
    except Exception as e:
        # 主函数级别的异常处理
        logger.error(get_text("execution_error", e))
        ui_display = get_ui_display()
        if ui_display:
            ui_display.show_message(get_text("execution_error", str(e)), "error")
            ui_display.close()
        sys.exit(1)


if __name__ == "__main__":
    main()
