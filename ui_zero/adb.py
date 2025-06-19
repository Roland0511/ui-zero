#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import time
from datetime import datetime
from typing import Tuple, Optional, List, Union, Callable
from .localization import get_text


class ADBTool:
    """
    ADB工具类，用于执行常见的ADB操作，如屏幕控制、截图、模拟输入等
    """

    def __init__(self, device_id: str = None):
        """
        初始化ADB工具类

        Args:
            device_id: 设备ID，如果有多个设备连接，需要指定
        """
        self.device_id = device_id
        self.auto_selected_device = False
        self._check_adb_available()
        self._auto_select_device_if_needed()

    def _check_adb_available(self) -> None:
        """检查ADB是否可用"""
        try:
            subprocess.run(
                ["adb", "version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            raise RuntimeError(get_text("adb_not_available"))

    def _auto_select_device_if_needed(self) -> None:
        """如果没有指定设备ID但有多个设备，自动选择第一个设备"""
        if self.device_id is None:
            devices = self.get_connected_devices()
            if len(devices) > 1:
                # 有多个设备，自动选择第一个
                self.device_id = devices[0]
                self.auto_selected_device = True
            elif len(devices) == 0:
                raise RuntimeError(get_text("no_devices_found"))

    def _build_command(self, cmd: List[str]) -> List[str]:
        """构建带有设备ID的ADB命令"""
        if self.device_id:
            return ["adb", "-s", self.device_id] + cmd
        return ["adb"] + cmd

    def execute_command(
        self, cmd: List[str], check: bool = True, text: bool = True
    ) -> subprocess.CompletedProcess:
        """
        执行ADB命令

        Args:
            cmd: 命令列表
            check: 是否检查命令执行状态

        Returns:
            命令执行结果
        """
        full_cmd = self._build_command(cmd)
        return subprocess.run(
            full_cmd,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
        )

    def get_connected_devices(self) -> List[str]:
        """
        获取已连接的设备列表

        Returns:
            设备ID列表
        """
        result = subprocess.run(
            ["adb", "devices"], check=True, stdout=subprocess.PIPE, text=True
        )
        lines = result.stdout.strip().split("\n")[
            1:
        ]  # 跳过第一行 "List of devices attached"
        devices = []

        for line in lines:
            if line.strip():
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    devices.append(parts[0])

        return devices

    def get_first_device(self) -> Optional[str]:
        """
        获取第一个连接的设备ID

        Returns:
            设备ID
        """
        devices = self.get_connected_devices()
        if self.device_id and self.device_id in devices:
            return self.device_id
        elif len(devices) > 0:
            return devices[0]
        else:
            return None

    def get_property(self, prop_name: str) -> str:
        """
        获取设备属性

        Args:
            prop_name: 属性名称

        Returns:
            属性值
        """
        result = self.execute_command(["shell", "getprop", prop_name])
        return result.stdout.strip()

    def list_properties(self) -> List[str]:
        """列出所有设备属性"""
        result = self.execute_command(["shell", "getprop"])
        return result.stdout.strip().split("\n")

    def get_device_model(self) -> str:
        """获取设备型号"""
        return self.get_property("ro.product.model")

    def get_device_market_name(self) -> str:
        """获取设备市场名称"""
        return self.get_property("ro.product.marketname")

    def set_screen_always_on(self, enable: bool = True) -> None:
        """
        设置屏幕常亮

        Args:
            enable: True 表示开启常亮，False 表示关闭常亮
        """
        if enable:
            self.execute_command(["shell", "svc", "power", "stayon", "true"])
        else:
            self.execute_command(["shell", "svc", "power", "stayon", "false"])

    def disable_screen_always_on(self) -> None:
        """取消屏幕常亮"""
        self.set_screen_always_on(False)

    def take_screenshot(self, output_path: str = None) -> str:
        """
        截取屏幕并保存到本地

        Args:
            output_path: 输出路径，如果为None则使用时间戳命名

        Returns:
            保存的图片路径
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            tmp_dir = os.path.join(os.getcwd(), "tmp")
            output_path = os.path.join(tmp_dir, f"screenshot_{timestamp}.png")

        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 正确获取PNG数据并保存
        result = self.execute_command(
            ["exec-out", "screencap", "-p"], check=True, text=False
        )
        with open(output_path, "wb") as f:
            f.write(result.stdout)

        return output_path

    def take_screenshot_to_bytes(self) -> bytes:
        """
        截取屏幕并返回图片字节数据

        Returns:
            图片字节数据
        """
        result = self.execute_command(
            ["exec-out", "screencap", "-p"], check=True, text=False
        )
        return result.stdout

    def tap(self, x: int, y: int) -> None:
        """
        模拟点击屏幕

        Args:
            x: 横坐标
            y: 纵坐标
        """
        self.execute_command(["shell", "input", "tap", str(x), str(y)])

    def double_tap(self, x: int, y: int) -> None:
        """
        模拟双击屏幕

        Args:
            x: 横坐标
            y: 纵坐标
        """
        self.tap(x, y)
        time.sleep(0.1)
        self.tap(x, y)

    def swipe(
        self, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int = 300
    ) -> None:
        """
        模拟滑动屏幕

        Args:
            start_x: 起始点横坐标
            start_y: 起始点纵坐标
            end_x: 结束点横坐标
            end_y: 结束点纵坐标
            duration_ms: 滑动持续时间（毫秒）
        """
        self.execute_command(
            [
                "shell",
                "input",
                "swipe",
                str(start_x),
                str(start_y),
                str(end_x),
                str(end_y),
                str(duration_ms),
            ]
        )

    def press_home(self) -> None:
        """模拟按下Home键"""
        self.execute_command(["shell", "input", "keyevent", "KEYCODE_HOME"])

    def press_back(self) -> None:
        """模拟按下返回键"""
        self.execute_command(["shell", "input", "keyevent", "KEYCODE_BACK"])

    def press_power(self) -> None:
        """模拟按下电源键"""
        self.execute_command(["shell", "input", "keyevent", "KEYCODE_POWER"])

    def press_volume_up(self) -> None:
        """模拟按下音量+键"""
        self.execute_command(["shell", "input", "keyevent", "KEYCODE_VOLUME_UP"])

    def press_volume_down(self) -> None:
        """模拟按下音量-键"""
        self.execute_command(["shell", "input", "keyevent", "KEYCODE_VOLUME_DOWN"])

    def input_text(self, text: str) -> None:
        """
        输入文本

        Args:
            text: 要输入的文本
        """
        # try switch to adbkeyboard
        # 检查是否安装ADB Keyboard
        result = self.execute_command(
            ["shell", "pm", "list", "packages", "com.android.adbkeyboard"], text=False
        )
        if result.returncode != 0:
            raise RuntimeError(
                "ADB Keyboard 未安装，请先安装 ADB Keyboard 应用:https://github.com/senzhk/ADBKeyBoard?tab=readme-ov-file"
            )
        try:
            # 切换输入法
            self.execute_command(
                ["shell", "ime", "enable", "com.android.adbkeyboard/.AdbIME"]
            )
            self.execute_command(
                ["shell", "ime", "set", "com.android.adbkeyboard/.AdbIME"]
            )
            # 等待输入法切换
            time.sleep(0.5)
            # adb shell am broadcast -a ADB_INPUT_TEXT --es msg '{text}'
            self.execute_command(
                [
                    "shell",
                    "am",
                    "broadcast",
                    "-a",
                    "ADB_INPUT_TEXT",
                    "--es",
                    "msg",
                    f'"{text}"',
                ]
            )
            time.sleep(0.5)  # 等待输入完成
            # 切换回原输入法
            # adb shell ime reset
            self.execute_command(["shell", "ime", "reset"])
        except Exception as e:
            # 使用日志系统记录错误
            from .logging_config import get_logger
            logger = get_logger("adb")
            logger.warning(get_text("adb_keyboard_input_failed").format(e))
            self.execute_command(["shell", "input", "text", f'"{text}"'])

    def get_screen_size(self) -> Tuple[int, int]:
        """
        获取屏幕尺寸

        Returns:
            (宽度, 高度) 元组
        """
        result = self.execute_command(["shell", "wm", "size"])
        # 解析输出，格式如: "Physical size: 1080x2340"
        size_str = result.stdout.strip()
        if "Physical size:" in size_str:
            dimensions = size_str.split("Physical size:")[1].strip().split("x")
            return int(dimensions[0]), int(dimensions[1])
        else:
            raise RuntimeError(get_text("failed_to_get_screen_size", size_str))

    def is_screen_on(self) -> bool:
        """
        检查屏幕是否点亮

        Returns:
            屏幕是否点亮
        """
        result = self.execute_command(
            ["shell", "dumpsys", "power", "|", "grep", "Display Power"]
        )
        return "state=ON" in result.stdout

    def wake_up(self) -> None:
        """唤醒设备（如果屏幕关闭）"""
        if not self.is_screen_on():
            self.press_power()
            time.sleep(1)  # 等待屏幕点亮

    def unlock_screen(self, swipe_up: bool = True) -> None:
        """
        解锁屏幕（简单滑动解锁）

        Args:
            swipe_up: 是否向上滑动解锁，如果为False则向右滑动
        """
        self.wake_up()
        width, height = self.get_screen_size()

        if swipe_up:
            # 从屏幕中下方向上滑动
            self.swipe(width // 2, height * 3 // 4, width // 2, height // 4, 300)
        else:
            # 从屏幕左侧向右滑动
            self.swipe(width // 4, height // 2, width * 3 // 4, height // 2, 300)

    def start_app(self, package_name: str, activity_name: Optional[str] = None) -> None:
        """
        启动应用

        Args:
            package_name: 应用包名
            activity_name: activity名称，如果为None则只启动包
        """
        if activity_name:
            self.execute_command(
                ["shell", "am", "start", "-n", f"{package_name}/{activity_name}"]
            )
        else:
            self.execute_command(
                [
                    "shell",
                    "monkey",
                    "-p",
                    package_name,
                    "-c",
                    "android.intent.category.LAUNCHER",
                    "1",
                ]
            )

    def stop_app(self, package_name: str) -> None:
        """
        停止应用

        Args:
            package_name: 应用包名
        """
        self.execute_command(["shell", "am", "force-stop", package_name])

    def get_current_activity(self) -> str:
        """
        获取当前活动

        Returns:
            当前活动名称
        """
        result = self.execute_command(
            [
                "shell",
                "dumpsys",
                "window",
                "windows",
                "|",
                "grep",
                "-E",
                "'mCurrentFocus|mFocusedApp'",
            ]
        )
        return result.stdout.strip()

    def long_press(self, x: int, y: int, duration_ms: int = 1000) -> None:
        """
        长按屏幕

        Args:
            x: 横坐标
            y: 纵坐标
            duration_ms: 按住时间（毫秒）
        """
        self.swipe(x, y, x, y, duration_ms)

    def multi_tap(self, x: int, y: int, count: int, interval_ms: int = 100) -> None:
        """
        连续点击

        Args:
            x: 横坐标
            y: 纵坐标
            count: 点击次数
            interval_ms: 点击间隔（毫秒）
        """
        for _ in range(count):
            self.tap(x, y)
            time.sleep(interval_ms / 1000)

    def drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int = 1000,
    ) -> None:
        """
        拖拽操作（与swipe相同，但通常用于表示拖拽UI元素）

        Args:
            start_x: 起始点横坐标
            start_y: 起始点纵坐标
            end_x: 结束点横坐标
            end_y: 结束点纵坐标
            duration_ms: 拖拽持续时间（毫秒）
        """
        self.swipe(start_x, start_y, end_x, end_y, duration_ms)

    def pinch_in(self, center_x: int, center_y: int, distance: int = 100) -> None:
        """
        捏合手势（缩小）

        Args:
            center_x: 中心点横坐标
            center_y: 中心点纵坐标
            distance: 手指移动距离
        """
        # 这是一个简化的实现，实际上需要使用多点触控API
        # 在某些设备上可能不起作用
        half_dist = distance // 2

        # 从外向内移动两个点
        self.execute_command(
            [
                "shell",
                "input",
                "touchscreen",
                "swipe",
                str(center_x - half_dist),
                str(center_y - half_dist),
                str(center_x),
                str(center_y),
                str(500),
            ]
        )

        self.execute_command(
            [
                "shell",
                "input",
                "touchscreen",
                "swipe",
                str(center_x + half_dist),
                str(center_y + half_dist),
                str(center_x),
                str(center_y),
                str(500),
            ]
        )

    def pinch_out(self, center_x: int, center_y: int, distance: int = 100) -> None:
        """
        张开手势（放大）

        Args:
            center_x: 中心点横坐标
            center_y: 中心点纵坐标
            distance: 手指移动距离
        """
        # 这是一个简化的实现，实际上需要使用多点触控API
        # 在某些设备上可能不起作用
        half_dist = distance // 2

        # 从内向外移动两个点
        self.execute_command(
            [
                "shell",
                "input",
                "touchscreen",
                "swipe",
                str(center_x),
                str(center_y),
                str(center_x - half_dist),
                str(center_y - half_dist),
                str(500),
            ]
        )

        self.execute_command(
            [
                "shell",
                "input",
                "touchscreen",
                "swipe",
                str(center_x),
                str(center_y),
                str(center_x + half_dist),
                str(center_y + half_dist),
                str(500),
            ]
        )

    def install_apk(self, apk_path: str) -> None:
        """
        安装APK

        Args:
            apk_path: APK文件路径
        """
        self.execute_command(["install", "-r", apk_path])

    def uninstall_app(self, package_name: str) -> None:
        """
        卸载应用

        Args:
            package_name: 应用包名
        """
        self.execute_command(["uninstall", package_name])

    def clear_app_data(self, package_name: str) -> None:
        """
        清除应用数据

        Args:
            package_name: 应用包名
        """
        self.execute_command(["shell", "pm", "clear", package_name])

    def reboot(self) -> None:
        """重启设备"""
        self.execute_command(["reboot"])

    def get_battery_info(self) -> dict:
        """
        获取电池信息

        Returns:
            电池信息字典
        """
        result = self.execute_command(["shell", "dumpsys", "battery"])
        lines = result.stdout.strip().split("\n")
        battery_info = {}

        for line in lines:
            line = line.strip()
            if ": " in line:
                key, value = line.split(": ", 1)
                battery_info[key] = value

        return battery_info

    def get_screen_stream(
        self,
        output_handler: Optional[Callable[[bytes], None]] = None,
        duration_sec: int = 10,
    ) -> None:
        """
        获取实时屏幕视频流并处理（默认播放，或传入处理函数）

        Args:
            output_handler: 可选的视频数据处理函数，接受 bytes 类型参数
            duration_sec: 捕捉持续时间（秒）
        """
        import threading

        def stream_reader(proc):
            try:
                while True:
                    chunk = proc.stdout.read(4096)
                    if not chunk:
                        break
                    if output_handler:
                        output_handler(chunk)
            finally:
                proc.stdout.close()

        full_cmd = self._build_command(
            ["exec-out", "screenrecord", "--output-format=h264", "-"]
        )
        proc = subprocess.Popen(
            full_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )

        thread = threading.Thread(target=stream_reader, args=(proc,))
        thread.start()

        try:
            time.sleep(duration_sec)
        finally:
            proc.terminate()
            thread.join()


def test():
    # 创建ADB工具实例
    adb = ADBTool()

    # 获取已连接设备
    devices = adb.get_connected_devices()
    print(get_text("connected_devices").format(devices))

    # 如果有设备连接，执行一些操作
    if devices:
        # 设置屏幕常亮
        adb.set_screen_always_on(True)
        print(get_text("screen_always_on_enabled"))

        # 截图并保存
        screenshot_path = adb.take_screenshot("test_screenshot.png")
        print(get_text("screenshot_saved").format(screenshot_path))

        # 模拟点击屏幕中心
        width, height = adb.get_screen_size()
        center_x, center_y = width // 2, height // 2
        adb.tap(center_x, center_y)
        print(get_text("tapped_center").format(center_x, center_y))

        # 模拟滑动
        adb.swipe(center_x, center_y + 200, center_x, center_y - 200, 500)
        print(get_text("swipe_up_completed"))

        # 按下Home键
        adb.press_home()
        print(get_text("home_key_pressed"))

        # 取消屏幕常亮
        adb.disable_screen_always_on()
        print(get_text("screen_always_on_disabled"))

        # 示例：获取实时流并播放（依赖 ffplay 或其他 handler）
        def handle_stream(data: bytes) -> None:
            # 缓存 H.264 数据到临时文件
            with open("stream_temp.h264", "ab") as f:
                f.write(data)

        print(get_text("screen_stream_starting"))
        # 清空临时文件
        if os.path.exists("stream_temp.h264"):
            os.remove("stream_temp.h264")
        adb.get_screen_stream(output_handler=handle_stream, duration_sec=10)
        print(get_text("screen_stream_ended"))

        # 使用 ffmpeg 将 h264 流转换为 png（保存第一帧）
        print(get_text("extracting_first_frame"))
        import ffmpeg

        (
            ffmpeg.input("stream_temp.h264")
            .output("stream_output.png", vframes=1)
            .run(overwrite_output=True)
        )
        print(get_text("saved_as_png"))


def test_type():
    adb = ADBTool()
    # adb.input_text("Hello, ADB!")
    adb.input_text("假日梦想家")


# 使用示例
if __name__ == "__main__":
    test_type()
