import asyncio
import builtins
import datetime
from typing import Any, Dict, Optional

from fastapi import WebSocket

from api.context import get_thread_context
from utils.logger_utils import logger


class ToolMonitor:
    """工具进度上报单例：统一向 WebSocket 推送工具调用、子智能体委派、最终结果等事件。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ToolMonitor, cls).__new__(cls)
            cls._instance.websocket_manager = None
        return cls._instance

    def set_websocket_manager(self, manager):
        self.websocket_manager = manager

    def _emit(self, event_type: str, message: str, data: Optional[Dict[str, Any]] = None):
        payload = {
            "type": "monitor_event",
            "event": event_type,
            "message": message,
            "data": data or {},
            "timestamp": datetime.datetime.now().isoformat(),
        }

        if self.websocket_manager:
            try:
                thread_id = get_thread_context()
                manager_loop = self.websocket_manager.loop
                if manager_loop and thread_id:
                    try:
                        current_loop = asyncio.get_running_loop()
                    except RuntimeError:
                        current_loop = None

                    if current_loop and current_loop == manager_loop:
                        current_loop.create_task(
                            self.websocket_manager.send_to_thread(payload, thread_id)
                        )
                    else:
                        # 跨线程时通过 run_coroutine_threadsafe 投递到目标循环
                        asyncio.run_coroutine_threadsafe(
                            self.websocket_manager.send_to_thread(payload, thread_id),
                            manager_loop,
                        )
            except Exception as e:
                logger.error(f"[Monitor] WebSocket send failed: {e}")

        # 脚本模式下通过全局 runtime 的 stream_writer 输出
        if builtins and hasattr(builtins, 'runtime') and hasattr(builtins.runtime, 'stream_writer'):
            try:
                builtins.runtime.stream_writer(payload)
            except Exception:
                pass

        logger.debug(f"[Monitor:{event_type}] {message}")

    def report_tool(self, tool_name: str, args: Dict[str, Any] = None):
        self._emit("tool_start", f"开始执行工具: {tool_name}", {"tool_name": tool_name, "args": args})

    def report_assistant(self, assistant_name: str, args: Dict[str, Any] = None):
        self._emit("assistant_call", f"正在调用助手: {assistant_name}",
                   {"assistant_name": assistant_name, "args": args})

    def report_task_result(self, result: str):
        self._emit("task_result", "任务执行完成", {"result": result})

    def report_session_dir(self, path: str):
        self._emit("session_created", f"工作目录已创建: {path}", {"path": path})


monitor = ToolMonitor()


class ConnectionManager:
    """WebSocket 连接管理：按 thread_id 维护连接，实现会话级消息隔离。"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.loop = None

    def set_loop(self, loop):
        self.loop = loop
        monitor.set_websocket_manager(self)
        logger.debug(f"[Monitor] ConnectionManager manually bound to loop: {id(self.loop)}")

    async def connect(self, websocket: WebSocket, thread_id: str):
        await websocket.accept()
        self.active_connections[thread_id] = websocket
        logger.debug(f"Client connected: {thread_id}")

    def disconnect(self, websocket: WebSocket, thread_id: str):
        if thread_id in self.active_connections:
            del self.active_connections[thread_id]
        logger.debug(f"Client disconnected: {thread_id}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def send_to_thread(self, message: dict, thread_id: str):
        if thread_id in self.active_connections:
            await self.active_connections[thread_id].send_json(message)


manager = ConnectionManager()
