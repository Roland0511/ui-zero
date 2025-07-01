#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
UI显示系统 - 使用rich库实现终端GUI界面
将终端也视为一种GUI界面，统一CLI和GUI模式的用户体验
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from .localization import get_text
from .logging_config import get_log_file


class UIDisplay:  # pylint: disable=too-many-instance-attributes
    """统一的UI显示系统，支持终端和GUI界面"""

    def __init__(self, is_terminal: bool = True):
        """
        初始化UI显示系统

        Args:
            is_terminal: 是否为终端模式
        """
        self.is_terminal = is_terminal
        self.console = Console() if is_terminal else None
        self.progress: Optional[Progress] = None
        self.live: Optional[Live] = None
        self.current_task: Optional[TaskID] = None
        self.tasks_info: List[Dict[str, Any]] = []
        self.current_step: int = 0
        self.ai_thinking_text: str = ""
        self.ai_thinking_clear_first: bool = True
        self.step_iterations: Dict[int, Optional[int]] = {}  # 记录每个步骤的剩余迭代次数
        self.stderr_messages: List[str] = []  # 存储错误输出信息
        self.max_stderr_lines: int = 10  # 最大显示的错误行数
        self.console_info: Dict[str, Any] = {}  # 存储控制台附加信息

    def initialize_progress(self, total_tasks: int, task_descriptions: List[str]):
        """初始化进度显示"""
        if not self.is_terminal:
            return

        self.tasks_info = [
            {"description": desc, "status": "pending"} for desc in task_descriptions
        ]

        # 创建进度条
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
        )

        # 添加主任务
        self.current_task = self.progress.add_task(
            get_text("overall_progress"), total=total_tasks
        )
        
        # 添加初始控制台信息
        self.add_console_info("start_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.add_console_info("total_tasks", total_tasks)

    def start_display(self):
        """开始显示界面"""
        if not self.is_terminal or self.progress is None:
            return

        # 创建实时显示的布局
        self.live = Live(self._create_layout(), console=self.console, refresh_per_second=4)
        self.live.start()

    def stop_display(self):
        """停止显示界面"""
        if self.live:
            self.live.stop()
            self.live = None

    def update_current_step(self, step_index: int, description: str, status: str = "running", left_iters: Optional[int] = None):
        """更新当前步骤"""
        self.current_step = step_index

        if step_index < len(self.tasks_info):
            self.tasks_info[step_index]["status"] = status

        # 记录剩余迭代次数
        if left_iters is not None:
            self.step_iterations[step_index] = left_iters

        if self.progress and self.current_task is not None:
            self.progress.update(
                self.current_task,
                description=f"{get_text('current_task')}: {description}",
                completed=step_index,
            )

        self._refresh_display()

    def complete_step(self, step_index: int):
        """完成当前步骤"""
        if step_index < len(self.tasks_info):
            self.tasks_info[step_index]["status"] = "completed"

        if self.progress and self.current_task is not None:
            self.progress.update(self.current_task, completed=step_index + 1)

        self._refresh_display()

    def update_ai_thinking(self, text: str, finished: bool = False):
        """更新AI思考过程"""
        if finished:
            self.ai_thinking_clear_first = True
        else:
            if self.ai_thinking_clear_first:
                # 如果是第一次更新，清空之前的内容
                self.ai_thinking_text = ""
                self.ai_thinking_clear_first = False
            # 累积追加新的思考内容
            self.ai_thinking_text += text
            # 限制显示长度，保留最后300个字符
            if len(self.ai_thinking_text) > 300:
                self.ai_thinking_text = self.ai_thinking_text[-300:]

        self._refresh_display(force=True)

    def show_message(self, message: str, level: str = "info"):
        """显示消息"""
        if not self.is_terminal or not self.console:
            # 在非终端模式下使用简单的print输出
            print(f"[{level.upper()}] {message}")
            return

        if level == "error":
            self.console.print(f"❌ {message}", style="red")
        elif level == "warning":
            self.console.print(f"⚠️  {message}", style="yellow")
        elif level == "success":
            self.console.print(f"✅ {message}", style="green")
        else:
            self.console.print(f"ℹ️  {message}", style="blue")

    def show_ai_response(self, text: str, finished: bool = False):
        """显示AI响应内容"""
        if not self.is_terminal:
            print(text, end="" if not finished else "\n", flush=True)
            return

        if finished:
            # AI响应完成，清空思考区域
            self.update_ai_thinking("", finished=True)
        else:
            # 实时更新AI思考内容
            self.update_ai_thinking(text)

    def _create_layout(self):
        """创建显示布局"""
        if not self.progress:
            return Panel(get_text("initializing_panel"))
        
        # 创建任务状态表格 - 使用比例控制宽度
        task_table = Table(show_header=True, header_style="bold magenta", expand=True)
        task_table.add_column(get_text("step_column"), style="dim", ratio=1, min_width=4)
        task_table.add_column(get_text("task_description_column"), ratio=8, min_width=20)
        task_table.add_column(get_text("status_column"), ratio=3, min_width=15)
        task_table.add_column(get_text("remaining_iterations_column"), justify="center", style="cyan", ratio=2, min_width=10)

        for i, task_info in enumerate(self.tasks_info):
            status_icon = self._get_status_icon(task_info["status"], i == self.current_step)
            
            # 获取剩余迭代次数显示
            left_iters_display = self._get_left_iters_display(i)
            
            task_table.add_row(
                str(i + 1), task_info["description"], status_icon, left_iters_display
            )

        # 创建AI思考区域
        ai_panel = self._create_ai_panel()

        # 创建控制台信息面板
        console_panel = self._create_console_panel()

        # 创建水平布局的底部面板区域 - 使用Table.grid确保50%:50%宽度分配
        bottom_panels = Table.grid(expand=True)
        bottom_panels.add_column(ratio=1, min_width=20)  # AI面板列 - 50%宽度
        bottom_panels.add_column(min_width=2, max_width=2)  # 间隔列 - 固定2字符
        bottom_panels.add_column(ratio=1, min_width=20)  # 控制台面板列 - 50%宽度
        bottom_panels.add_row(ai_panel, "", console_panel)

        # 组合布局 - 使用全终端宽度
        layout = Table.grid(expand=True)
        layout.add_column(ratio=1)  # 单列，占满全宽
        layout.add_row(self.progress)
        layout.add_row()
        layout.add_row(task_table)
        layout.add_row()
        layout.add_row(bottom_panels)

        return layout

    def _get_status_icon(self, status: str, is_current: bool) -> str:
        """获取状态图标"""
        if is_current and status == "running":
            return f"[bold yellow]🔄 {get_text('status_executing')}[/bold yellow]"
        if status == "completed":
            return f"[bold green]✅ {get_text('status_completed')}[/bold green]"
        if status == "error":
            return f"[bold red]❌ {get_text('status_error')}[/bold red]"
        if status == "running":
            return f"[bold blue]▶️ {get_text('status_running')}[/bold blue]"
        return f"[dim]⏳ {get_text('status_waiting')}[/dim]"

    def _get_left_iters_display(self, step_index: int) -> str:
        """获取剩余迭代次数显示"""
        if step_index in self.step_iterations:
            left_iters = self.step_iterations[step_index]
            if left_iters is not None:
                if left_iters == 0:
                    return "[dim]0[/dim]"
                elif left_iters <= 3:
                    return f"[bold red]{left_iters}[/bold red]"
                elif left_iters <= 6:
                    return f"[bold yellow]{left_iters}[/bold yellow]"
                else:
                    return f"[bold green]{left_iters}[/bold green]"
        
        # 对于未开始的步骤，显示默认值
        task_info = self.tasks_info[step_index] if step_index < len(self.tasks_info) else None
        if task_info and task_info["status"] == "completed":
            return "[dim]0[/dim]"
        elif task_info and task_info["status"] == "running":
            return "[bold cyan]?[/bold cyan]"
        else:
            return "[dim]-[/dim]"
        
    def _create_ai_panel(self) -> Panel:
        """创建AI思考过程面板"""
        # 构建AI思考内容
        ai_content = []
        
        # 添加状态信息
        current_time = datetime.now().strftime("%H:%M:%S")
        ai_content.append(f"[bold cyan]Current Time:[/bold cyan] {current_time}")
        
        # 添加当前步骤信息
        if self.current_step < len(self.tasks_info):
            current_task = self.tasks_info[self.current_step]["description"]
            ai_content.append(f"[bold green]Current Task:[/bold green] {current_task}")
        
        ai_content.append("")  # 空行分隔
        
        # 显示AI思考内容
        if self.ai_thinking_text:
            # 将思考内容按行分割并限制显示行数
            thinking_lines = self.ai_thinking_text.strip().split('\n')
            max_thinking_lines = 4
            if len(thinking_lines) > max_thinking_lines:
                display_lines = thinking_lines[-max_thinking_lines:]
                ai_content.append("[dim]...[/dim]")  # 表示有更多内容
            else:
                display_lines = thinking_lines
            
            for line in display_lines:
                # 截断过长的行
                if len(line) > 80:
                    line = line[:77] + "..."
                ai_content.append(f"[italic]{line}[/italic]")
        else:
            ai_content.append(f"[dim]{get_text('thinking_placeholder')}[/dim]")
        
        ai_text = "\n".join(ai_content)
        
        return Panel(
            Text.from_markup(ai_text),
            title=get_text("thinking_process_title"),
            title_align="left",
            border_style="blue",
            height=8,  # 固定高度
        )

    def _create_console_panel(self) -> Panel:
        """创建控制台信息面板"""
        # 获取日志文件路径
        log_file_path = get_log_file()
        log_path_text = str(log_file_path) if log_file_path else "N/A"
        
        # 构建控制台内容
        console_content = []
        console_content.append(f"[bold cyan]{get_text('log_file_path')}:[/bold cyan] {log_path_text}")
        
        # 显示日志文件大小（如果存在）
        if log_file_path and Path(log_file_path).exists():
            try:
                file_size = Path(log_file_path).stat().st_size
                size_kb = file_size / 1024
                console_content.append(f"[dim]Size: {size_kb:.1f} KB[/dim]")
            except Exception:
                pass
        
        # 显示控制台信息
        if self.console_info:
            for key, value in self.console_info.items():
                if key == "start_time":
                    console_content.append(f"[dim]Started: {value}[/dim]")
                elif key == "total_tasks":
                    console_content.append(f"[dim]Total tasks: {value}[/dim]")
                else:
                    console_content.append(f"[dim]{key}: {value}[/dim]")
        
        # 显示最近的错误信息或日志信息
        if self.stderr_messages:
            recent_errors = self.stderr_messages[-self.max_stderr_lines:]
            for error_msg in recent_errors:
                console_content.append(f"[red]{error_msg.strip()}[/red]")
        else:
            # 尝试读取最近的日志条目
            recent_logs = self._get_recent_log_entries()
            if recent_logs:
                for log_entry in recent_logs:
                    console_content.append(f"[dim]{log_entry}[/dim]")
            else:
                console_content.append(f"[green]{get_text('no_stderr_output')}[/green]")
        
        console_text = "\n".join(console_content)
        
        return Panel(
            Text.from_markup(console_text),
            title=get_text("console_panel_title"),
            title_align="left",
            border_style="red",
            height=8,  # 固定高度
        )
    
    def _get_recent_log_entries(self, max_lines: int = 3) -> List[str]:
        """获取最近的日志条目"""
        log_file_path = get_log_file()
        if not log_file_path or not Path(log_file_path).exists():
            return []
        
        try:
            with open(log_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # 获取最后几行，去掉换行符
                recent_lines = [line.strip() for line in lines[-max_lines:] if line.strip()]
                # 截断太长的行
                truncated_lines = []
                for line in recent_lines:
                    if len(line) > 80:
                        truncated_lines.append(line[:77] + "...")
                    else:
                        truncated_lines.append(line)
                return truncated_lines
        except Exception:
            return []

    def add_stderr_message(self, message: str):
        """添加错误信息到控制台面板"""
        if message.strip():
            self.stderr_messages.append(message)
            # 保持最大数量限制
            if len(self.stderr_messages) > 50:  # 保持最近50条错误信息
                self.stderr_messages = self.stderr_messages[-50:]
            self._refresh_display(force=True)

    def clear_stderr_messages(self):
        """清空错误信息"""
        self.stderr_messages.clear()
        self._refresh_display(force=True)
    
    def add_console_info(self, key: str, value: Any):
        """添加控制台信息"""
        self.console_info[key] = value
        self._refresh_display(force=True)
    
    def remove_console_info(self, key: str):
        """移除控制台信息"""
        if key in self.console_info:
            del self.console_info[key]
            self._refresh_display(force=True)

    def _refresh_display(self, force: bool = False):
        """刷新显示"""
        if self.live:
            self.live.update(self._create_layout(), refresh=force)

    def finalize(self, success: bool = True):
        """完成所有任务"""
        if self.progress and self.current_task is not None:
            final_desc = (
                get_text("all_tasks_completed") 
                if success 
                else get_text("execution_failed")
            )
            self.progress.update(
                self.current_task,
                description=final_desc,
                completed=len(self.tasks_info),
            )

        self._refresh_display()
        time.sleep(1)  # 让用户看到最终状态

    def close(self):
        """关闭UI显示"""
        self.stop_display()

    def export_task_table_to_json(self) -> Dict[str, Any]:
        """导出任务表格数据为JSON格式"""
        export_data = {
            "metadata": {
                "export_time": datetime.now().isoformat(),
                "total_tasks": len(self.tasks_info),
                "current_step": self.current_step,
                "console_info": self.console_info.copy()
            },
            "tasks": []
        }
        
        for i, task_info in enumerate(self.tasks_info):
            task_data = {
                "step": i + 1,
                "description": task_info["description"],
                "status": task_info["status"],
                "remaining_iterations": self.step_iterations.get(i),
                "is_current": i == self.current_step
            }
            export_data["tasks"].append(task_data)
        
        return export_data


# 全局UI显示实例
_ui_display: Optional[UIDisplay] = None


def get_ui_display() -> Optional[UIDisplay]:
    """获取全局UI显示实例"""
    return _ui_display


def initialize_ui_display(is_terminal: bool = True) -> UIDisplay:
    """初始化全局UI显示系统"""
    global _ui_display  # pylint: disable=global-statement
    _ui_display = UIDisplay(is_terminal=is_terminal)
    return _ui_display


def show_message(message: str, level: str = "info"):
    """显示消息的便捷函数"""
    ui = get_ui_display()
    if ui:
        ui.show_message(message, level)
    else:
        print(f"[{level.upper()}] {message}")


def show_ai_response(text: str, finished: bool = False):
    """显示AI响应的便捷函数"""
    ui = get_ui_display()
    if ui:
        ui.show_ai_response(text, finished)
    else:
        print(text, end="" if not finished else "\n", flush=True)


def add_stderr_message(message: str):
    """添加错误信息的便捷函数"""
    ui = get_ui_display()
    if ui:
        ui.add_stderr_message(message)
    else:
        print(f"[STDERR] {message}", file=sys.stderr)


def clear_stderr_messages():
    """清空错误信息的便捷函数"""
    ui = get_ui_display()
    if ui:
        ui.clear_stderr_messages()


def add_console_info(key: str, value: Any):
    """添加控制台信息的便捷函数"""
    ui = get_ui_display()
    if ui:
        ui.add_console_info(key, value)


def remove_console_info(key: str):
    """移除控制台信息的便捷函数"""
    ui = get_ui_display()
    if ui:
        ui.remove_console_info(key)


def export_execution_results_to_json(output_file: str):
    """将执行结果导出为JSON文件"""
    ui = get_ui_display()
    if ui:
        try:
            export_data = ui.export_task_table_to_json()
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"导出JSON文件失败: {e}")
            return False
    else:
        print("无法获取执行结果数据")
        return False
