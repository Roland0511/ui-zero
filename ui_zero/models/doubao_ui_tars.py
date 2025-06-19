"""DoubaoUITarsModel implementation for UI automation using ByteDance's UI-TARS model."""

import base64
import io
import json
import math
import os
import re
from pathlib import Path
from typing import Callable, Optional

import matplotlib.pyplot as plt
from openai import OpenAI
from PIL import Image, ImageDraw

from .arkmodel import ArkModel
from ..localization import get_text

SYSTEM_PROMPT = """
    You are a GUI agent. You are given a task and your action history, with screenshots. You need to perform the next action to complete the task. 
    ## Output Format
    ```
    Thought: ...
    Action: ...
    ```
    ## Action Space

    click(point='<point>x1 y1</point>')
    double_click(point='<point>x1 y1</point>') #Usually used to scale images on mobile devices.
    long_press(point='<point>x1 y1</point>')
    type(content='') #If you want to submit your input, use "\\n" at the end of `content`.
    drag(start_point='<point>x1 y1</point>', end_point='<point>x2 y2</point>')
    press_home()
    press_back()
    wait() #Sleep for 2s and take a screenshot to check for any changes.
    finished(content='xxx') # Use escape characters \\', \\", and \\n in content part to ensure we can parse the content in normal python string format.


    ## Note
    - Use {language} in `Thought` part.
    - Write a small plan and finally summarize your next action (with its target element) in one sentence in `Thought` part.

    ## User Instruction
    {instruction}
"""
MODEL_NAME = "doubao-1-5-ui-tars-250428"


class ActionOutput:
    """
    封装模型动作输出的类

    属性:
        thought (str): 模型的思考过程
        action (str): 动作类型，如click, long_press, type等
        point (list): 点击坐标 [x, y]，范围0-1000，用于click, long_press, scroll等动作
        start_point (list): 起始点坐标 [x, y]，范围0-1000，用于drag动作
        end_point (list): 结束点坐标 [x, y]，范围0-1000，用于drag动作
        app_name (str): 应用名称，用于open_app动作
        content (str): 内容，用于type和finished动作
        point_abs (list): 点击绝对坐标 [x, y]，单位像素
        start_point_abs (list): 起始点绝对坐标 [x, y]，单位像素
        end_point_abs (list): 结束点绝对坐标 [x, y]，单位像素
    """

    def __init__(
        self,
        thought="",
        action="",
        point=None,
        start_point=None,
        end_point=None,
        app_name=None,
        content=None,
        point_abs=None,
        start_point_abs=None,
        end_point_abs=None,
    ):
        self.thought = thought
        self.action = action
        self.point = point
        self.start_point = start_point
        self.end_point = end_point
        self.app_name = app_name
        self.content = content
        self.point_abs = point_abs
        self.start_point_abs = start_point_abs
        self.end_point_abs = end_point_abs

    def __str__(self):
        """返回对象的字符串表示"""
        return (
            f"ActionOutput(action={self.action}, "
            f"point={self.point}, start_point={self.start_point}, end_point={self.end_point}, "
            f"app_name={self.app_name}, "
            f"content={self.content if self.content is None else repr(self.content)})"
        )

    def __repr__(self):
        """返回对象的官方字符串表示"""
        return self.__str__()

    def to_dict(self):
        """将对象转换为字典"""
        return {
            "thought": self.thought,
            "action": self.action,
            "point": self.point,
            "start_point": self.start_point,
            "end_point": self.end_point,
            "app_name": self.app_name,
            "content": self.content,
            "point_abs": self.point_abs,
            "start_point_abs": self.start_point_abs,
            "end_point_abs": self.end_point_abs,
        }

    @classmethod
    def from_dict(cls, data):
        """从字典创建对象"""
        return cls(
            thought=data.get("thought", ""),
            action=data.get("action", ""),
            point=data.get("point"),
            start_point=data.get("start_point"),
            end_point=data.get("end_point"),
            app_name=data.get("app_name"),
            content=data.get("content"),
            point_abs=data.get("point_abs"),
            start_point_abs=data.get("start_point_abs"),
            end_point_abs=data.get("end_point_abs"),
        )

    def has_coordinates(self):
        """检查是否包含坐标信息"""
        return (
            self.point is not None
            or self.start_point is not None
            or self.end_point is not None
        )

    def is_click_action(self):
        """检查是否为点击动作"""
        return self.action == "click"

    def is_double_click_action(self):
        """检查是否为双击动作"""
        return self.action == "double_click"

    def is_long_press_action(self):
        """检查是否为长按动作"""
        return self.action == "long_press"

    def is_open_app_action(self):
        """检查是否为打开应用动作"""
        return self.action == "open_app"

    def is_drag_action(self):
        """检查是否为拖拽动作"""
        return self.action == "drag"

    def is_press_home_action(self):
        """检查是否为按下Home键动作"""
        return self.action == "press_home"

    def is_press_back_action(self):
        """检查是否为按下返回键动作"""
        return self.action == "press_back"

    def is_press_power_action(self):
        """检查是否为按下电源键动作"""
        return self.action == "press_power"

    def is_type_action(self):
        """检查是否为键盘输入动作"""
        return self.action == "type"

    def is_wait_action(self):
        """检查是否为等待动作"""
        return self.action == "wait"

    def is_finished(self):
        """检查是否为完成动作"""
        return self.action == "finished"


def point_to_box(point, box_size=10):
    """
    将点坐标转换为边界框坐标

    参数:
        point: 点坐标 [x, y]
        box_size: 边界框大小

    返回:
        边界框坐标 [x1, y1, x2, y2]
    """
    x, y = point
    half_size = box_size // 2
    return [x - half_size, y - half_size, x + half_size, y + half_size]


def coordinates_convert(point, img_size):
    """
    将相对坐标[0,1000]转换为图片上的绝对像素坐标

    参数:
        point: 相对坐标列表/元组 [x, y] (范围0-1000)
        img_size: 图片尺寸元组 (width, height)

    返回:
        绝对坐标列表 [x, y] (单位:像素)

    示例:
        >>> coordinates_convert([500, 500], (1000, 2000))
        [500, 1000]  # 对于2000高度的图片，y坐标×2
    """
    # 参数校验
    if len(point) != 2 or len(img_size) != 2:
        raise ValueError(get_text("point_conversion_invalid_format"))

    # 解包图片尺寸
    img_width, img_height = img_size

    # 计算绝对坐标
    abs_x = int(point[0] * img_width / 1000)
    abs_y = int(point[1] * img_height / 1000)

    return [abs_x, abs_y]


def parse_action_output(output_text):
    # 提取Thought部分 - 支持 "Action:" 和 "Next action:" 两种格式
    thought_match = re.search(
        r"Thought:(.*?)(?:\n(?:Action|Next action):)", output_text, re.DOTALL
    )
    thought = thought_match.group(1).strip() if thought_match else ""

    # 提取Action部分 - 优先匹配 "Action:"，如果没有再匹配 "Next action:"
    action_match = re.search(r"Action:(.*?)(?:\n|$)", output_text, re.DOTALL)
    if not action_match:
        action_match = re.search(r"Next action:(.*?)(?:\n|$)", output_text, re.DOTALL)
    action_text = action_match.group(1).strip() if action_match else ""

    # 创建ActionOutput对象
    result = ActionOutput(thought=thought)

    if not action_text:
        return result

    # 解析action类型
    action_parts = action_text.split("(", 1)
    action_type = action_parts[0].strip()
    result.action = action_type

    # 如果没有参数部分，直接返回
    if len(action_parts) == 1 or not action_parts[1].strip():
        return result

    # 解析参数
    params_text = action_parts[1].rstrip(")")

    # 处理不同类型的动作
    if action_type in ["click", "long_press", "scroll", "double_click"]:
        # 提取point参数
        point_match = re.search(r"point='<point>(.*?)</point>'", params_text)
        if point_match:
            point_str = point_match.group(1)
            coords = [int(x) for x in point_str.split()]
            if len(coords) == 2:
                result.point = coords

    elif action_type == "drag":
        # 提取start_point参数
        start_point_match = re.search(
            r"start_point='<point>(.*?)</point>'", params_text
        )
        if start_point_match:
            start_point_str = start_point_match.group(1)
            start_coords = [int(x) for x in start_point_str.split()]
            if len(start_coords) == 2:
                result.start_point = start_coords

        # 提取end_point参数
        end_point_match = re.search(r"end_point='<point>(.*?)</point>'", params_text)
        if end_point_match:
            end_point_str = end_point_match.group(1)
            end_coords = [int(x) for x in end_point_str.split()]
            if len(end_coords) == 2:
                result.end_point = end_coords

    elif action_type == "open_app":
        # 提取app_name参数
        app_name_match = re.search(r"app_name='(.*?)'", params_text)
        if app_name_match:
            result.app_name = app_name_match.group(1)

    elif action_type in ["type", "finished"]:
        # 提取content参数
        content_match = re.search(r"content='(.*?)'(?:,|$)", params_text)
        if content_match:
            content = content_match.group(1)
            # 处理转义字符
            content = (
                content.replace("\\n", "\n").replace('\\"', '"').replace("\\'", "'")
            )
            result.content = content

    return result


def image_to_base64(image_path_or_bytes):
    ext: Optional[str] = None
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".svg": "image/svg+xml",
    }

    binary_data: Optional[bytes] = None
    if isinstance(image_path_or_bytes, bytes):
        # 如果是字节流，直接使用
        binary_data = image_path_or_bytes
        if not ext:
            # 尝试从字节流中推断扩展名
            if binary_data.startswith(b"\x89PNG"):
                ext = ".png"
            elif binary_data.startswith(b"\xff\xd8"):
                ext = ".jpg"
            elif binary_data.startswith(b"GIF"):
                ext = ".gif"
            elif binary_data.startswith(b"<?xml") and b"<svg" in binary_data:
                ext = ".svg"
            else:
                ext = ".png"
    elif isinstance(image_path_or_bytes, str):
        # 如果是字符串路径，读取文件
        if not os.path.exists(image_path_or_bytes):
            raise FileNotFoundError(
                get_text("image_file_not_found", image_path_or_bytes)
            )
        if not ext:
            ext = Path(image_path_or_bytes).suffix.lower()
        with open(image_path_or_bytes, "rb") as image_file:
            binary_data = image_file.read()
    else:
        raise TypeError(get_text("image_input_invalid_type"))

    base64_data = base64.b64encode(binary_data).decode("utf-8")
    return f"data:{mime_types.get(ext, 'image/png')};base64,{base64_data}"


def draw_box_and_show(image, start_point=None, end_point=None):
    """
    在图片上绘制点、线和箭头

    参数:
        image: PIL.Image对象或图片路径
        start_point: 起始点坐标 [x, y] (绝对坐标)
        end_point: 结束点坐标 [x, y] (绝对坐标)
    """
    point_color = "red"
    arrow_color = "blue"
    point_size = 10
    line_width = 5
    # drag_arrow_length = 150  # drag操作箭头长度 - currently unused

    draw = ImageDraw.Draw(image)

    # 绘制起始点和结束点，以及它们之间的连接
    if start_point is not None:
        x, y = start_point
        radius = point_size
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=point_color)

        if end_point is not None:
            # 绘制结束点
            x, y = end_point
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius), fill=point_color
            )

            # 绘制两点之间的连接线和箭头
            draw.line([start_point, end_point], fill=arrow_color, width=line_width)
            draw_arrow_head(draw, start_point, end_point, arrow_color, point_size * 3)

    # 显示结果图片
    plt.imshow(image)
    plt.axis("on")  # 显示坐标轴
    plt.show()


def draw_arrow_head(draw, start, end, color, size):
    """
    绘制箭头头部
    """
    # 计算角度
    angle = math.atan2(end[1] - start[1], end[0] - start[0])

    # 计算箭头三个点的位置
    p1 = end
    p2 = (
        end[0] - size * math.cos(angle + math.pi / 6),
        end[1] - size * math.sin(angle + math.pi / 6),
    )
    p3 = (
        end[0] - size * math.cos(angle - math.pi / 6),
        end[1] - size * math.sin(angle - math.pi / 6),
    )

    # 绘制箭头
    draw.polygon([p1, p2, p3], fill=color)


def calculate_drag_endpoint(start_point, direction, length):
    """
    计算drag操作的箭头终点

    参数:
        start_point: 起点坐标 (x, y)
        direction: 方向 ('up', 'down', 'left', 'right')
        length: 箭头长度

    返回:
        终点坐标 (x, y)
    """
    x, y = start_point
    if direction == "up":
        return (x, y - length)
    elif direction == "down":
        return (x, y + length)
    elif direction == "left":
        return (x - length, y)
    elif direction == "right":
        return (x + length, y)
    else:
        return (x, y)  # 默认不移动


class DoubaoUITarsModel(ArkModel):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        super().__init__(MODEL_NAME, SYSTEM_PROMPT, api_key, base_url)

    def run(
        self,
        user_prompt: str,
        image: Optional[str | bytes] = None,
        stream_resp_callback: Optional[Callable[[str, bool], None]] = None,
        debug: bool = False,
    ) -> ActionOutput:
        """运行模型并返回解析后的动作输出"""
        # 如果没有提供图片路径，返回空的ActionOutput
        if image is None:
            return ActionOutput()

        try:
            # 创建API客户端
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)

            # 构建请求参数
            messages = []

            # 添加系统消息
            messages.append({"role": "system", "content": self.system_prompt})

            # 构建用户消息内容
            user_content = []
            user_content.append({"type": "text", "text": user_prompt})

            # 添加图片
            user_content.append(
                {"type": "image_url", "image_url": {"url": image_to_base64(image)}}
            )

            # 添加用户消息
            messages.append({"role": "user", "content": user_content})

            # 发送请求
            stream = client.chat.completions.create(
                model=self.model_name, temperature=0, messages=messages, stream=True
            )
            # OpenAI stream processing

            full_response: str = ""
            stream_finished = False
            # 处理流式响应
            for chunk in stream:
                # cc:ChatCompletionChunk = chunk
                if debug:
                    from ..logging_config import get_logger
                    logger = get_logger("doubao_ui_tars")
                    logger.debug(get_text("model_response_chunk").format(chunk))
                # 处理分块响应
                if (
                    chunk.choices
                    and chunk.choices[0].delta
                    and chunk.choices[0].delta.content
                ):
                    response_content = chunk.choices[0].delta.content
                    full_response += response_content
                    if stream_resp_callback:
                        is_finish = chunk.choices[0].finish_reason is not None
                        stream_resp_callback(response_content, is_finish)
                        if stream_finished is False and is_finish:
                            stream_finished = True

            if stream_finished is False:
                # 如果最后一个流式响应没有finish_reason，补充一个结束符
                if stream_resp_callback:
                    stream_resp_callback("\n", True)

            # 提取响应文本
            model_response = ""
            if full_response:
                # 去除多余的空格和换行
                model_response = full_response.strip()

            if not model_response:
                from ..logging_config import get_logger
                logger = get_logger("doubao_ui_tars")
                logger.warning(get_text("model_response_empty"))
                return ActionOutput()

            if debug:
                from ..logging_config import get_logger
                logger = get_logger("doubao_ui_tars")
                logger.debug(get_text("model_response_debug").format(model_response))
            # 解析输出
            parsed_output = parse_action_output(model_response)

            # 转换坐标
            if isinstance(image, str):
                # 如果是图片路径，获取图片尺寸
                img = Image.open(image)
            elif isinstance(image, bytes):
                # 如果是字节流，创建Image对象
                img = Image.open(io.BytesIO(image))
            else:
                raise TypeError(get_text("image_input_invalid_type"))
            if parsed_output.point:
                parsed_output.point_abs = coordinates_convert(
                    parsed_output.point, img.size
                )
            if parsed_output.start_point:
                parsed_output.start_point_abs = coordinates_convert(
                    parsed_output.start_point, img.size
                )
            if parsed_output.end_point:
                parsed_output.end_point_abs = coordinates_convert(
                    parsed_output.end_point, img.size
                )

            return parsed_output

        except Exception as e:
            from ..logging_config import get_logger
            logger = get_logger("doubao_ui_tars")
            logger.error(get_text("api_error").format(e))
            return ActionOutput()

    def show_debug_box(self, image_path: str, parsed_output: ActionOutput):
        if not image_path or not parsed_output:
            from ..logging_config import get_logger
            logger = get_logger("doubao_ui_tars")
            logger.warning(get_text("debug_box_missing_data"))
            return

        try:
            image = Image.open(image_path)
            start_point_abs = None
            end_point_abs = None

            if parsed_output.start_point:
                start_point_abs = coordinates_convert(
                    parsed_output.start_point, image.size
                )
            elif parsed_output.point:
                start_point_abs = coordinates_convert(parsed_output.point, image.size)
            if parsed_output.end_point:
                end_point_abs = coordinates_convert(parsed_output.end_point, image.size)

            draw_box_and_show(image, start_point_abs, end_point_abs)
        except Exception as e:
            from ..logging_config import get_logger
            logger = get_logger("doubao_ui_tars")
            logger.error(get_text("debug_box_error").format(e))
