"""Android UI automation agent module."""

import time
from typing import Callable, Optional

from .adb import ADBTool
from .localization import get_text
from .logging_config import get_logger
from .models import DoubaoUITarsModel as UIModel, ActionOutput

# 获取agent模块的logger
logger = get_logger("agent")


def take_action(adb: ADBTool, output: ActionOutput):
    """Execute action based on model output."""
    if output.is_click_action():
        if output.point_abs is not None:
            adb.tap(output.point_abs[0], output.point_abs[1])
    elif output.is_double_click_action():
        if output.point_abs is not None:
            adb.double_tap(output.point_abs[0], output.point_abs[1])
    elif output.is_long_press_action():
        if output.point_abs is not None:
            adb.long_press(output.point_abs[0], output.point_abs[1])
    elif output.is_drag_action():
        if output.start_point_abs is not None and output.end_point_abs is not None:
            adb.drag(
                output.start_point_abs[0],
                output.start_point_abs[1],
                output.end_point_abs[0],
                output.end_point_abs[1],
                500,
            )
    elif output.is_type_action():
        if output.content is not None:
            adb.input_text(output.content)
    elif output.is_press_back_action():
        adb.press_back()
    elif output.is_press_home_action():
        adb.press_home()
    elif output.is_press_power_action():
        adb.press_power()
    elif output.is_wait_action():
        # Wait action with duration from content field (in milliseconds)
        # If no content specified, use default 2000ms (2 seconds)
        if output.content:
            duration_ms = int(output.content)
        else:
            duration_ms = 2000  # Default 2 seconds

        duration_seconds = duration_ms / 1000.0
        logger.info(get_text("waiting_for_ms", duration_ms))
        time.sleep(duration_seconds)
    else:
        logger.warning(get_text("unsupported_action", output.action))


class AndroidAgent:
    """Android Agent for UI testing."""

    def __init__(self, adb: Optional[ADBTool] = None, model: Optional[UIModel] = None):
        """Initialize the agent with ADB tool and model."""
        self.adb = adb or ADBTool()
        self.model = model or UIModel()

    def _build_prompt_with_history(self, original_prompt: str, history: list) -> str:
        """构建包含历史信息的完整prompt"""
        if not history:
            return original_prompt

        # 构建历史记录部分
        history_text = "\n## Action History\n"
        for i, (_, step_output) in enumerate(history, 1):
            history_text += f"Step {i}:\n"
            history_text += f"Thought: {step_output.thought}\n"
            history_text += f"Action: {step_output.action}"

            # 添加动作参数信息
            if step_output.point is not None:
                history_text += f"(point='<point>{step_output.point[0]} {step_output.point[1]}</point>')"
            elif (
                step_output.start_point is not None
                and step_output.end_point is not None
            ):
                history_text += f"(start_point='<point>{step_output.start_point[0]} {step_output.start_point[1]}</point>', end_point='<point>{step_output.end_point[0]} {step_output.end_point[1]}</point>')"
            elif step_output.content is not None:
                history_text += f"(content='{step_output.content}')"
            elif step_output.app_name is not None:
                history_text += f"(app_name='{step_output.app_name}')"
            else:
                history_text += "()"

            history_text += "\n\n"

        # 组合完整prompt
        full_prompt = f"{history_text}\n## Current Task\n{original_prompt}"
        return full_prompt

    def run(
        self,
        prompt: str,
        max_iters: int = 10,
        screenshot_callback: Optional[Callable[[bytes], None]] = None,
        preaction_callback: Optional[Callable[[str, ActionOutput], None]] = None,
        postaction_callback: Optional[Callable[[str, ActionOutput, int], None]] = None,
        stream_resp_callback: Optional[Callable[[str, bool], None]] = None,
        include_history: bool = True,
        debug: bool = False,
        timeout: Optional[int] = None,
    ) -> ActionOutput:
        """Run the agent with the given prompt."""
        # print(f"Running agent with prompt: {prompt}")
        try:
            self.adb.set_screen_always_on(True)
            output = None
            history = []  # 存储历史执行记录
            current_iter = 0
            start_time = time.time()

            while max_iters > 0:
                current_iter += 1

                # 检查是否超时
                if timeout is not None:
                    elapsed_time = (time.time() - start_time) * 1000  # 转换为毫秒
                    if elapsed_time > timeout:
                        logger.warning(get_text("timeout_exceeded", timeout))
                        return ActionOutput(
                            thought=get_text("timeout_exceeded_thought", timeout),
                            action="timeout",
                            content=get_text(
                                "timeout_exceeded_content", timeout, elapsed_time
                            ),
                        )

                # Take a screenshot
                img_bytes = self.adb.take_screenshot_to_bytes()
                if screenshot_callback:
                    screenshot_callback(img_bytes)

                # 构建包含历史信息的prompt
                if include_history:
                    full_prompt = self._build_prompt_with_history(prompt, history)
                else:
                    full_prompt = prompt

                if debug:
                    logger.debug(get_text("debug_full_prompt", current_iter))
                    logger.debug(get_text("prompt_separator"))
                    logger.debug(full_prompt)
                    logger.debug(get_text("prompt_separator"))

                # Run the model
                output = self.model.run(
                    full_prompt,
                    img_bytes,
                    stream_resp_callback=stream_resp_callback,
                    debug=debug,
                )

                # 将当前步骤添加到历史记录中
                history.append((prompt, output))

                if preaction_callback:
                    preaction_callback(prompt, output)

                # Take action based on the output
                if output.is_finished():
                    # print(f"Action finished: {output}")
                    break

                take_action(self.adb, output)
                max_iters -= 1
                if postaction_callback:
                    postaction_callback(prompt, output, max_iters)
                # sleep to allow the action to take effect
                time.sleep(0.3)

            return output or ActionOutput(action="wait", content="No action taken")
        except Exception as e:
            self.adb.set_screen_always_on(False)
            raise e


if __name__ == "__main__":
    # 命令行调用
    import argparse

    parser = argparse.ArgumentParser(description="Run Android Agent.")
    parser.add_argument(
        "--prompt", type=str, required=True, help="Prompt for the agent."
    )
    parser.add_argument("--max_iters", type=int, default=5, help="Maximum iterations.")
    args = parser.parse_args()
    agent = AndroidAgent()
    agent.run(args.prompt, args.max_iters)
