import asyncio
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent.main_agent import run_deep_agent
from api.monitor import manager
from utils.logger_utils import logger

_project_root = Path(__file__).resolve().parent.parent

app = FastAPI(title="DeepAgents API")

_output_dir = _project_root / "output"
_output_dir.mkdir(exist_ok=True)

_upload_dir = _project_root / "upload"
_upload_dir.mkdir(exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskRequest(BaseModel):
    query: str
    thread_id: Optional[str] = None


@app.get("/api/health")
async def health_check():
    """健康检查，返回固定的 status 字段供探针判断服务存活。"""
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    """启动时把事件循环绑定到 WebSocket 管理器，供后台线程安全投递消息。"""
    loop = asyncio.get_running_loop()
    manager.set_loop(loop)
    logger.debug(f"[Server] WebSocket Manager bound to loop: {id(loop)}")


@app.post("/api/task")
async def run_task(request: TaskRequest):
    """提交任务：后台异步执行 Agent，立即返回会话 ID。"""
    thread_id = request.thread_id or str(uuid.uuid4())
    asyncio.create_task(run_deep_agent(request.query, thread_id))
    return {"status": "started", "thread_id": thread_id}


@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...), thread_id: str = Form(...)):
    """上传文件到 upload/session_{thread_id}，供后续任务读取。"""
    target_dir = _upload_dir / f"session_{thread_id}"
    target_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for file in files:
        # 只取文件名部分，避免路径穿越
        safe_name = Path(file.filename or "").name
        if not safe_name:
            continue
        file_path = target_dir / safe_name
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        saved_files.append(safe_name)

    return {"status": "uploaded", "files": saved_files}


@app.get("/api/download")
async def download_file(path: str):
    """下载文件，仅允许 output 目录内的路径。"""
    try:
        abs_path = Path(path).resolve()
        output_abs = _output_dir.resolve()
        if not abs_path.is_relative_to(output_abs):
            logger.error(f"[Server] 拒绝下载越界路径: {abs_path}")
            return {"error": "拒绝访问: 只能下载输出目录下的文件"}
    except Exception:
        logger.error(f"[Server] 无效的下载路径: {path}")
        return {"error": "无效的路径参数"}

    if not abs_path.exists():
        return {"error": "文件不存在"}

    return FileResponse(abs_path, filename=abs_path.name)


@app.get("/api/files")
async def list_files(path: str):
    """列出 output 目录下指定路径的所有文件及其元数据。"""
    try:
        abs_path = Path(path).resolve()
        output_abs = _output_dir.resolve()
        if not abs_path.is_relative_to(output_abs):
            logger.error(f"[Server] 拒绝访问: {abs_path} 不在 {output_abs} 目录下")
            return {"error": "拒绝访问: 只能访问输出目录下的文件"}
    except Exception as e:
        logger.error(f"[Server] 路径解析失败: {e}")
        return {"error": f"路径无效: {e}"}

    if not abs_path.exists():
        return {"error": "目录不存在"}

    files = []
    try:
        for file_path in abs_path.rglob("*"):
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    "name": file_path.name,
                    "type": "file",
                    "path": str(file_path),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                })
    except Exception as e:
        logger.error(f"[Server] 遍历文件失败: {e}")
        return {"error": str(e)}

    files.sort(key=lambda x: x.get("mtime", 0), reverse=True)
    return {"files": files}


@app.websocket("/ws/{thread_id}")
async def websocket_endpoint(websocket: WebSocket, thread_id: str):
    """会话级 WebSocket：接收心跳并回复 pong，连接断开时清理。"""
    await manager.connect(websocket, thread_id)

    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({
                "type": "pong",
                "message": f"服务端已收到: {data}",
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket, thread_id)
        logger.debug(f"[Server] 客户端已断开: {thread_id}")
    except Exception as e:
        logger.error(f"[Server] WebSocket 连接异常: {e}")
        manager.disconnect(websocket, thread_id)


def start_server():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    start_server()
