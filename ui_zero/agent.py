import time
from .models import DoubaoUITarsModel as UIModel, ActionOutput
from .adb import ADBTool
from .localization import get_text
from typing import Callable, Optional
import threading


def take_action(adb: ADBTool, output: ActionOutput):
    if output.is_click_action():
        adb.tap(output.point_abs[0], output.point_abs[1])
    elif output.is_double_click_action():
        adb.double_tap(output.point_abs[0], output.point_abs[1])
    elif output.is_long_press_action():
        adb.long_press(output.point_abs[0], output.point_abs[1])
    elif output.is_drag_action():
        adb.drag(
            output.start_point_abs[0],
            output.start_point_abs[1],
            output.end_point_abs[0],
            output.end_point_abs[1],
            500,
        )
    elif output.is_type_action():
        adb.input_text(output.content)
    elif output.is_press_back_action():
        adb.press_back()
    elif output.is_press_home_action():
        adb.press_home()
    elif output.is_press_power_action():
        adb.press_power()
    elif output.is_wait_action():
        wait_time = 2  # Default wait time
        print(get_text("waiting_seconds", wait_time))
        time.sleep(wait_time)
    else:
        print(get_text("unsupported_action", output.action))


class AndroidAgent:
    """Android Agent for UI testing."""

    def __init__(self, adb: ADBTool = None, model: UIModel = None):
        """Initialize the agent with ADB tool and model."""
        self.adb = adb or ADBTool()
        self.model = model or UIModel()

    def _build_prompt_with_history(self, original_prompt: str, history: list) -> str:
        """构建包含历史信息的完整prompt"""
        if not history:
            return original_prompt

        # 构建历史记录部分
        history_text = "\n## Action History\n"
        for i, (step_prompt, step_output) in enumerate(history, 1):
            history_text += f"Step {i}:\n"
            history_text += f"Thought: {step_output.thought}\n"
            history_text += f"Action: {step_output.action}"

            # 添加动作参数信息
            if step_output.point:
                history_text += f"(point='<point>{step_output.point[0]} {step_output.point[1]}</point>')"
            elif step_output.start_point and step_output.end_point:
                history_text += f"(start_point='<point>{step_output.start_point[0]} {step_output.start_point[1]}</point>', end_point='<point>{step_output.end_point[0]} {step_output.end_point[1]}</point>')"
            elif step_output.content:
                history_text += f"(content='{step_output.content}')"
            elif step_output.app_name:
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
        postaction_callback: Optional[Callable[[str, ActionOutput], None]] = None,
        stream_resp_callback: Optional[Callable[[str, bool], None]] = None,
        include_history: bool = True,
        debug: bool = False,
    ) -> ActionOutput:
        """Run the agent with the given prompt."""
        # print(f"Running agent with prompt: {prompt}")
        try:
            self.adb.set_screen_always_on(True)
            output = None
            history = []  # 存储历史执行记录
            current_iter = 0

            while max_iters > 0:
                current_iter += 1

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
                    print(get_text("debug_full_prompt", current_iter))
                    print(get_text("prompt_separator"))
                    print(full_prompt)
                    print(get_text("prompt_separator"))

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
                if postaction_callback:
                    postaction_callback(prompt, output)
                max_iters -= 1
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
