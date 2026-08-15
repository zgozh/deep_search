from contextvars import ContextVar
from typing import Optional

# 异步场景下的会话隔离：多个请求在同一个事件循环里并发执行，普通全局变量会相互串数据。
# ContextVar 提供协程级（task 级）的局部变量，保证每个请求链路读到的都是自己的会话上下文。
_session_dir_ctx: ContextVar[Optional[str]] = ContextVar("session_dir", default=None)
_thread_id_ctx: ContextVar[Optional[str]] = ContextVar("thread_id", default=None)


def set_session_context(path: str):
    """写入当前请求的会话工作目录，返回 token 供 reset 恢复。"""
    return _session_dir_ctx.set(path)


def get_session_context() -> Optional[str]:
    """读取当前请求的会话工作目录。"""
    return _session_dir_ctx.get()


def set_thread_context(thread_id: str):
    """写入当前请求的会话 ID。"""
    return _thread_id_ctx.set(thread_id)


def get_thread_context() -> Optional[str]:
    """读取当前请求的会话 ID。"""
    return _thread_id_ctx.get()


def reset_session_context(session_token, thread_token=None):
    """请求结束时重置上下文，防止污染后续请求。"""
    _session_dir_ctx.reset(session_token)
    if thread_token:
        _thread_id_ctx.reset(thread_token)