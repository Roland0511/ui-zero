#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
UI-Zero API Server
提供REST API和WebSocket接口，允许通过HTTP请求和实时WebSocket连接使用UI-Zero的所有功能
"""

import asyncio
import base64
import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
import threading

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from .adb import ADBTool
from .agent import ActionOutput
from .cli import (
    run_testcases,
    execute_single_step,
    list_available_devices,
    convert_yaml_to_testcases,
)
from .env_config import ensure_env_config
from .localization import get_text
from .logging_config import get_logger

# 获取server模块的logger
logger = get_logger("server")


# API Models
class DeviceInfo(BaseModel):
    """设备信息模型"""

    device_id: str = Field(..., description="设备ID", example="ABC123DEF456")
    model: Optional[str] = Field(None, description="设备型号", example="Pixel 7")
    market_name: Optional[str] = Field(
        None, description="设备市场名称", example="Google Pixel 7"
    )

    class Config:
        schema_extra = {
            "example": {
                "device_id": "ABC123DEF456",
                "model": "Pixel 7",
                "market_name": "Google Pixel 7",
            }
        }


class CommandRequest(BaseModel):
    """单命令执行请求"""

    command: str = Field(
        ..., description="要执行的命令", example="find and click settings icon"
    )
    device_id: Optional[str] = Field(
        None, description="指定设备ID", example="ABC123DEF456"
    )
    timeout: Optional[int] = Field(None, description="超时时间（毫秒）", example=30000)

    class Config:
        schema_extra = {
            "example": {
                "command": "find and click settings icon",
                "device_id": "ABC123DEF456",
                "timeout": 30000,
            }
        }


class TestCaseRequest(BaseModel):
    """测试用例执行请求"""

    test_cases: List[str] = Field(
        ...,
        description="测试用例列表",
        example=["find and click settings", "scroll to bottom", "click about phone"],
    )
    device_id: Optional[str] = Field(
        None, description="指定设备ID", example="ABC123DEF456"
    )
    include_history: bool = Field(True, description="是否包含历史记录")
    debug: bool = Field(False, description="是否启用调试模式")

    class Config:
        schema_extra = {
            "example": {
                "test_cases": [
                    "find and click settings",
                    "scroll to bottom",
                    "click about phone",
                ],
                "device_id": "ABC123DEF456",
                "include_history": True,
                "debug": False,
            }
        }


class YamlTestCaseRequest(BaseModel):
    """YAML测试用例执行请求"""

    yaml_config: Dict[str, Any] = Field(..., description="YAML配置内容")
    device_id: Optional[str] = Field(
        None, description="指定设备ID（覆盖YAML中的配置）", example="ABC123DEF456"
    )
    include_history: bool = Field(True, description="是否包含历史记录")
    debug: bool = Field(False, description="是否启用调试模式")

    class Config:
        schema_extra = {
            "example": {
                "yaml_config": {
                    "android": {"deviceId": "ABC123DEF456"},
                    "tasks": [
                        {
                            "name": "Settings Test",
                            "flow": [
                                {"ai": "find and click settings"},
                                {"sleep": 2000},
                                {"aiAssert": "settings page is visible"},
                            ],
                        }
                    ],
                },
                "include_history": True,
                "debug": False,
            }
        }


class ExecutionResponse(BaseModel):
    """执行响应"""

    session_id: str = Field(..., description="执行会话ID", example="uuid-session-id")
    status: str = Field(..., description="执行状态", example="started")
    message: str = Field(
        ..., description="状态消息", example="Command execution started"
    )

    class Config:
        schema_extra = {
            "example": {
                "session_id": "uuid-session-id",
                "status": "started",
                "message": "Command execution started",
            }
        }


class ActionOutputResponse(BaseModel):
    """动作输出响应"""

    thought: str = Field("", description="AI思考过程")
    action: str = Field("", description="执行的动作")
    point: Optional[List[int]] = Field(None, description="点击坐标")
    start_point: Optional[List[int]] = Field(None, description="起始坐标")
    end_point: Optional[List[int]] = Field(None, description="结束坐标")
    content: Optional[str] = Field(None, description="内容")
    is_finished: bool = Field(False, description="是否已完成")


class WebSocketMessage(BaseModel):
    """WebSocket消息模型"""

    type: str = Field(..., description="消息类型")
    session_id: str = Field(..., description="会话ID")
    data: Dict[str, Any] = Field(..., description="消息数据")
    timestamp: str = Field(..., description="时间戳")


# WebSocket连接管理器
class ConnectionManager:
    """WebSocket连接管理器，负责管理活跃连接和会话连接"""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.session_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: Optional[str] = None):
        """连接WebSocket并分配连接ID"""
        await websocket.accept()
        connection_id = str(uuid.uuid4())

        if connection_id not in self.active_connections:
            self.active_connections[connection_id] = []
        self.active_connections[connection_id].append(websocket)

        if session_id:
            if session_id not in self.session_connections:
                self.session_connections[session_id] = []
            self.session_connections[session_id].append(websocket)

        return connection_id

    def disconnect(self, connection_id: str, session_id: Optional[str] = None):
        """断开WebSocket连接"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

        if session_id and session_id in self.session_connections:
            # Remove websocket from session connections
            self.session_connections[session_id] = [
                ws
                for ws in self.session_connections[session_id]
                if ws not in self.active_connections.get(connection_id, [])
            ]
            if not self.session_connections[session_id]:
                del self.session_connections[session_id]

    async def send_to_session(self, session_id: str, message: WebSocketMessage):
        """向指定会话发送消息"""
        if session_id in self.session_connections:
            dead_connections = []
            for websocket in self.session_connections[session_id]:
                try:
                    await websocket.send_text(message.model_dump_json())
                except Exception as e:
                    dead_connections.append(websocket)
                    logger.warning(f"Failed to send message to websocket: {e}")

            # Remove dead connections
            for dead_ws in dead_connections:
                self.session_connections[session_id] = [
                    ws for ws in self.session_connections[session_id] if ws != dead_ws
                ]

    async def broadcast(self, message: WebSocketMessage):
        """广播消息到所有连接"""
        for connections in self.active_connections.values():
            for websocket in connections:
                try:
                    await websocket.send_text(message.model_dump_json())
                except Exception:
                    pass


# 全局变量
manager = ConnectionManager()
active_sessions: Dict[str, Dict[str, Any]] = {}

# 创建FastAPI应用
app = FastAPI(
    title="UI-Zero API Server",
    description=get_text("api_server_description"),
    version="0.1.8",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 回调函数，用于将执行状态发送到WebSocket
async def create_websocket_callbacks(session_id: str):
    """创建WebSocket回调函数"""

    async def screenshot_callback(img_bytes: bytes):
        # 将截图编码为base64并发送
        img_base64 = base64.b64encode(img_bytes).decode("utf-8")
        message = WebSocketMessage(
            type="screenshot",
            session_id=session_id,
            data={"image": f"data:image/png;base64,{img_base64}"},
            timestamp=datetime.now().isoformat(),
        )
        await manager.send_to_session(session_id, message)

    async def preaction_callback(prompt: str, output: ActionOutput):
        message = WebSocketMessage(
            type="preaction",
            session_id=session_id,
            data={
                "prompt": prompt,
                "action_output": {
                    "thought": output.thought,
                    "action": output.action,
                    "point": output.point,
                    "start_point": output.start_point,
                    "end_point": output.end_point,
                    "content": output.content,
                },
            },
            timestamp=datetime.now().isoformat(),
        )
        await manager.send_to_session(session_id, message)

    async def postaction_callback(prompt: str, output: ActionOutput, left_iters: int):
        message = WebSocketMessage(
            type="postaction",
            session_id=session_id,
            data={
                "prompt": prompt,
                "action_output": {
                    "thought": output.thought,
                    "action": output.action,
                    "point": output.point,
                    "start_point": output.start_point,
                    "end_point": output.end_point,
                    "content": output.content,
                },
                "left_iterations": left_iters,
            },
            timestamp=datetime.now().isoformat(),
        )
        await manager.send_to_session(session_id, message)

    async def stream_resp_callback(content: str, is_finish: bool):
        message = WebSocketMessage(
            type="stream_response",
            session_id=session_id,
            data={"content": content, "is_finish": is_finish},
            timestamp=datetime.now().isoformat(),
        )
        await manager.send_to_session(session_id, message)

    return (
        screenshot_callback,
        preaction_callback,
        postaction_callback,
        stream_resp_callback,
    )


# API路由
@app.get("/")
async def root():
    """根路径，返回API信息"""
    return {
        "name": "UI-Zero API Server",
        "version": "0.1.8",
        "description": get_text("api_server_description"),
        "endpoints": {
            "devices": "/devices",
            "command": "/command",
            "testcase": "/testcase",
            "yaml_testcase": "/yaml_testcase",
            "websocket": "/ws/{session_id}",
            "health": "/health",
            "documentation": "/docs",
            "redoc": "/redoc",
        },
    }


@app.get(
    "/health",
    tags=["Health"],
    summary="健康检查",
    description="检查API服务器状态和环境配置",
)
async def health_check():
    """健康检查端点，返回服务器状态和环境配置情况"""
    # 检查环境配置
    env_valid = ensure_env_config(skip_interactive=True)

    return {
        "status": "healthy" if env_valid else "warning",
        "environment_configured": env_valid,
        "active_sessions": len(active_sessions),
        "timestamp": datetime.now().isoformat(),
    }


@app.get(
    "/devices",
    response_model=List[DeviceInfo],
    tags=["Device Management"],
    summary="获取设备列表",
    description="列出所有连接的Android设备及其信息",
)
async def get_devices():
    """获取连接的Android设备列表，包括设备ID、型号和市场名称"""
    try:
        device_ids = list_available_devices()
        devices = []

        for device_id in device_ids:
            try:
                adb_tool = ADBTool(device_id=device_id)
                model = adb_tool.get_device_model()
                market_name = adb_tool.get_device_market_name()
                devices.append(
                    DeviceInfo(
                        device_id=device_id, model=model, market_name=market_name
                    )
                )
            except Exception as e:
                logger.warning(get_text("device_info_error", device_id, e))
                devices.append(
                    DeviceInfo(device_id=device_id, model=None, market_name=None)
                )

        return devices
    except Exception as e:
        logger.error(get_text("device_list_error", e))
        raise HTTPException(status_code=500, detail=str(e))


# 辅助函数：创建异步回调的同步包装器
def create_sync_callbacks(main_loop, session_id, callbacks, queues):
    """创建同步回调包装器，用于在线程中调用"""
    screenshot_callback, preaction_callback, postaction_callback, stream_resp_callback = callbacks
    screenshot_queue, preaction_queue, postaction_queue, stream_resp_queue = queues
    
    def sync_screenshot_callback(img_bytes: bytes):
        try:
            asyncio.run_coroutine_threadsafe(
                screenshot_queue.put(img_bytes), main_loop
            )
        except Exception as e:
            logger.error(f"Screenshot callback error: {e}")
    
    def sync_preaction_callback(prompt: str, output):
        try:
            asyncio.run_coroutine_threadsafe(
                preaction_queue.put((prompt, output)), main_loop
            )
        except Exception as e:
            logger.error(f"Preaction callback error: {e}")
    
    def sync_postaction_callback(prompt: str, output, left_iters: int):
        try:
            asyncio.run_coroutine_threadsafe(
                postaction_queue.put((prompt, output, left_iters)), main_loop
            )
        except Exception as e:
            logger.error(f"Postaction callback error: {e}")
    
    def sync_stream_resp_callback(content: str, is_finish: bool):
        try:
            logger.info(f"Streaming response: {content}, finished: {is_finish}")
            asyncio.run_coroutine_threadsafe(
                stream_resp_queue.put((content, is_finish)), main_loop
            )
        except Exception as e:
            logger.error(f"Stream response callback error: {e}")
    
    return (
        sync_screenshot_callback,
        sync_preaction_callback,
        sync_postaction_callback,
        sync_stream_resp_callback,
    )


# 辅助函数：创建队列处理器
async def create_queue_processor(session_id, callbacks, queues):
    """创建队列处理器，用于在主线程中处理来自工作线程的消息"""
    screenshot_callback, preaction_callback, postaction_callback, stream_resp_callback = callbacks
    screenshot_queue, preaction_queue, postaction_queue, stream_resp_queue = queues
    
    while session_id in active_sessions and active_sessions[session_id]["status"] in ["running"]:
        try:
            if not screenshot_queue.empty():
                img_bytes = await screenshot_queue.get()
                await screenshot_callback(img_bytes)
                
            if not preaction_queue.empty():
                prompt, output = await preaction_queue.get()
                await preaction_callback(prompt, output)
                
            if not postaction_queue.empty():
                prompt, output, left_iters = await postaction_queue.get()
                await postaction_callback(prompt, output, left_iters)
                
            if not stream_resp_queue.empty():
                content, is_finish = await stream_resp_queue.get()
                await stream_resp_callback(content, is_finish)
                
            await asyncio.sleep(0.01)  # 短暂休眠避免CPU占用过高
        except Exception as e:
            logger.error(f"Error processing queue: {e}")
            await asyncio.sleep(0.1)
    
    logger.info(f"Queue processor for session {session_id} stopped")


@app.post(
    "/command",
    response_model=ExecutionResponse,
    tags=["Command Execution"],
    summary="执行单个命令",
    description="执行单个UI自动化命令并返回会话ID",
)
async def execute_command(request: CommandRequest):
    """执行单个UI自动化命令，支持设备选择和超时设置"""
    session_id = str(uuid.uuid4())

    try:
        # 检查环境配置
        if not ensure_env_config(skip_interactive=True):
            raise HTTPException(
                status_code=400, detail=get_text("env_config_incomplete_invalid")
            )

        # 记录执行会话
        active_sessions[session_id] = {
            "type": "command",
            "status": "running",
            "start_time": datetime.now(),
            "request": request.model_dump(),
        }

        # 创建主线程中的回调函数
        main_loop = asyncio.get_event_loop()
        callbacks = await create_websocket_callbacks(session_id)
        
        # 创建线程安全的队列用于跨线程通信
        queues = (
            asyncio.Queue(),  # screenshot_queue
            asyncio.Queue(),  # preaction_queue
            asyncio.Queue(),  # postaction_queue
            asyncio.Queue(),  # stream_resp_queue
        )
        
        # 创建同步回调包装器
        sync_callbacks = create_sync_callbacks(main_loop, session_id, callbacks, queues)
        
        # 启动队列处理任务
        queue_task = asyncio.create_task(create_queue_processor(session_id, callbacks, queues))
        
        def run_command():
            result = None
            try:
                result = execute_single_step(
                    request.command,
                    device_id=request.device_id,
                    timeout=request.timeout,
                    screenshot_callback=sync_callbacks[0],
                    preaction_callback=sync_callbacks[1],
                    postaction_callback=sync_callbacks[2],
                    stream_resp_callback=sync_callbacks[3],
                )
            except Exception as e:
                logger.error(get_text("command_execution_error", e))
                active_sessions[session_id].update(
                    {"status": "failed", "error": str(e), "end_time": datetime.now()}
                )
                return
            
            # 更新会话状态
            if result:
                active_sessions[session_id].update(
                    {
                        "status": "completed",
                        "result": {
                            "thought": result.thought,
                            "action": result.action,
                            "point": result.point,
                            "start_point": result.start_point,
                            "end_point": result.end_point,
                            "content": result.content,
                            "is_finished": result.is_finished(),
                        },
                        "end_time": datetime.now(),
                    }
                )
            else:
                active_sessions[session_id].update(
                    {"status": "failed", "error": "No result returned", "end_time": datetime.now()}
                )

        thread = threading.Thread(target=run_command)
        thread.start()

        return ExecutionResponse(
            session_id=session_id,
            status="started",
            message=get_text("command_execution_started"),
        )

    except Exception as e:
        logger.error(get_text("command_execution_error", e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/testcase",
    response_model=ExecutionResponse,
    tags=["Test Case Execution"],
    summary="执行测试用例",
    description="执行一系列测试用例命令",
)
async def execute_testcase(request: TestCaseRequest):
    """执行一系列测试用例命令，支持历史记录和调试模式"""
    session_id = str(uuid.uuid4())

    try:
        # 检查环境配置
        if not ensure_env_config(skip_interactive=True):
            raise HTTPException(
                status_code=400, detail=get_text("env_config_incomplete_invalid")
            )

        # 转换为统一格式
        testcase_prompts = [
            {
                "type": "ai_action",
                "prompt": cmd,
                "continueOnError": False,
                "taskName": get_text("command_number", i + 1),
            }
            for i, cmd in enumerate(request.test_cases)
        ]

        # 记录执行会话
        active_sessions[session_id] = {
            "type": "testcase",
            "status": "running",
            "start_time": datetime.now(),
            "request": request.model_dump(),
            "total_steps": len(testcase_prompts),
            "current_step": 0,
        }

        # 创建主线程中的回调函数
        main_loop = asyncio.get_event_loop()
        callbacks = await create_websocket_callbacks(session_id)
        
        # 创建线程安全的队列用于跨线程通信
        queues = (
            asyncio.Queue(),  # screenshot_queue
            asyncio.Queue(),  # preaction_queue
            asyncio.Queue(),  # postaction_queue
            asyncio.Queue(),  # stream_resp_queue
        )
        
        # 创建同步回调包装器
        sync_callbacks = create_sync_callbacks(main_loop, session_id, callbacks, queues)
        
        # 启动队列处理任务
        queue_task = asyncio.create_task(create_queue_processor(session_id, callbacks, queues))
        
        def run_testcase():
            try:
                run_testcases(
                    testcase_prompts,
                    include_history=request.include_history,
                    debug=request.debug,
                    device_id=request.device_id,
                    screenshot_callback=sync_callbacks[0],
                    preaction_callback=sync_callbacks[1],
                    postaction_callback=sync_callbacks[2],
                    stream_resp_callback=sync_callbacks[3],
                )
                
                active_sessions[session_id].update(
                    {"status": "completed", "end_time": datetime.now()}
                )
            except Exception as e:
                logger.error(get_text("testcase_execution_error", e))
                active_sessions[session_id].update(
                    {"status": "failed", "error": str(e), "end_time": datetime.now()}
                )

        thread = threading.Thread(target=run_testcase)
        thread.start()

        return ExecutionResponse(
            session_id=session_id,
            status="started",
            message=get_text("testcase_execution_started"),
        )

    except Exception as e:
        logger.error(get_text("testcase_execution_error", e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/yaml_testcase",
    response_model=ExecutionResponse,
    tags=["Test Case Execution"],
    summary="执行YAML测试用例",
    description="执行YAML格式的复杂测试用例配置",
)
async def execute_yaml_testcase(request: YamlTestCaseRequest):
    """执行YAML格式的复杂测试用例配置，支持多任务、断言和等待操作"""
    session_id = str(uuid.uuid4())

    try:
        # 检查环境配置
        if not ensure_env_config(skip_interactive=True):
            raise HTTPException(
                status_code=400, detail=get_text("env_config_incomplete_invalid")
            )

        # 转换YAML配置为测试用例
        testcase_prompts, device_id_from_config = convert_yaml_to_testcases(
            request.yaml_config
        )
        final_device_id = request.device_id or device_id_from_config

        # 记录执行会话
        active_sessions[session_id] = {
            "type": "yaml_testcase",
            "status": "running",
            "start_time": datetime.now(),
            "request": request.model_dump(),
            "total_steps": len(testcase_prompts),
            "current_step": 0,
        }

        # 创建主线程中的回调函数
        main_loop = asyncio.get_event_loop()
        callbacks = await create_websocket_callbacks(session_id)
        
        # 创建线程安全的队列用于跨线程通信
        queues = (
            asyncio.Queue(),  # screenshot_queue
            asyncio.Queue(),  # preaction_queue
            asyncio.Queue(),  # postaction_queue
            asyncio.Queue(),  # stream_resp_queue
        )
        
        # 创建同步回调包装器
        sync_callbacks = create_sync_callbacks(main_loop, session_id, callbacks, queues)
        
        # 启动队列处理任务
        queue_task = asyncio.create_task(create_queue_processor(session_id, callbacks, queues))
        
        def run_yaml_testcase():
            try:
                run_testcases(
                    testcase_prompts,
                    include_history=request.include_history,
                    debug=request.debug,
                    device_id=final_device_id,
                    screenshot_callback=sync_callbacks[0],
                    preaction_callback=sync_callbacks[1],
                    postaction_callback=sync_callbacks[2],
                    stream_resp_callback=sync_callbacks[3],
                )
                
                active_sessions[session_id].update(
                    {"status": "completed", "end_time": datetime.now()}
                )
            except Exception as e:
                logger.error(get_text("yaml_testcase_execution_error", e))
                active_sessions[session_id].update(
                    {"status": "failed", "error": str(e), "end_time": datetime.now()}
                )

        thread = threading.Thread(target=run_yaml_testcase)
        thread.start()

        return ExecutionResponse(
            session_id=session_id,
            status="started",
            message=get_text("yaml_testcase_execution_started"),
        )

    except Exception as e:
        logger.error(get_text("yaml_testcase_execution_error", e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/session/{session_id}",
    tags=["Session Management"],
    summary="获取会话状态",
    description="获取指定会话的执行状态和结果",
)
async def get_session_status(session_id: str):
    """获取指定会话的执行状态、进度和结果"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail=get_text("session_not_found"))

    session = active_sessions[session_id]
    return {
        "session_id": session_id,
        "type": session["type"],
        "status": session["status"],
        "start_time": session["start_time"].isoformat(),
        "end_time": (
            session.get("end_time", {}).isoformat() if session.get("end_time") else None
        ),
        "current_step": session.get("current_step", 0),
        "total_steps": session.get("total_steps", 1),
        "result": session.get("result"),
        "error": session.get("error"),
    }


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket端点，用于实时执行反馈

    连接后可以接收以下类型的消息：
    - connected: 连接确认
    - screenshot: 实时截图（base64编码）
    - preaction: 动作执行前的状态
    - postaction: 动作执行后的状态
    - stream_response: AI模型流式响应
    - ping/pong: 心跳消息
    """
    connection_id = await manager.connect(websocket, session_id)

    try:
        # 发送连接确认消息
        welcome_message = WebSocketMessage(
            type="connected",
            session_id=session_id,
            data={"message": get_text("websocket_connected")},
            timestamp=datetime.now().isoformat(),
        )
        await websocket.send_text(welcome_message.model_dump_json())

        # 保持连接活跃
        while True:
            try:
                # 等待客户端消息（心跳包等）
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)

                # 处理客户端消息
                try:
                    client_message = json.loads(data)
                    if client_message.get("type") == "ping":
                        pong_message = WebSocketMessage(
                            type="pong",
                            session_id=session_id,
                            data={"message": "pong"},
                            timestamp=datetime.now().isoformat(),
                        )
                        await websocket.send_text(pong_message.model_dump_json())
                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                # 发送心跳
                ping_message = WebSocketMessage(
                    type="ping",
                    session_id=session_id,
                    data={"message": "ping"},
                    timestamp=datetime.now().isoformat(),
                )
                await websocket.send_text(ping_message.model_dump_json())

    except WebSocketDisconnect:
        logger.info(get_text("websocket_disconnected", session_id))
    except Exception as e:
        logger.error(get_text("websocket_error", session_id, e))
    finally:
        manager.disconnect(connection_id, session_id)


# 服务器启动函数
def start_server(host: str = "0.0.0.0", port: int = 8000, log_level: str = "info"):
    """启动API服务器"""
    logger.info(get_text("server_starting", host, port))

    # 检查环境配置
    if not ensure_env_config(skip_interactive=True):
        logger.error(get_text("env_config_incomplete_invalid"))
        return False

    try:
        uvicorn.run(app, host=host, port=port, log_level=log_level)
        return True
    except Exception as e:
        logger.error(get_text("server_start_error", e))
        return False


if __name__ == "__main__":
    start_server()
