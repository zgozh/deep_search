from utils.logger_utils import logger
import os

from pathlib import Path
from typing import Optional

def resolve_path(filename: str, session_dir: Optional[str] = None) -> str:
    """
    统一的文件路径解析，返回绝对路径。

    处理规则：
    1. 清洗虚拟路径前缀（/workspace、/mnt/data、/home/user）
    2. 路径含 upload/ 时，相对于项目根目录解析
    3. 相对路径拼接到 session_dir，保证会话内路径隔离
    4. 修正 session_{id}/session_{id} 之类的重复嵌套
    """
    path = Path(filename)
    path_str = filename.replace("\\", "/")

    # 虚拟路径前缀清洗
    virtual_prefixes = ["/workspace", "/mnt/data", "/home/user"]
    for prefix in virtual_prefixes:
        if path_str.startswith(prefix):
            cleaned = path_str[len(prefix):].lstrip("/")
            path = Path(cleaned)
            path_str = str(path).replace("\\", "/")
            break

    # upload/ 目录统一相对项目根目录解析
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    if "upload/" in path_str:
        idx = path_str.find("upload/")
        return str(PROJECT_ROOT / path_str[idx:])

    if not session_dir:
        return str(path.resolve())

    session_path = Path(session_dir).resolve()
    session_name = session_path.name

    is_unix_abs = path_str.startswith("/")

    if path.is_absolute() or (os.name == 'nt' and is_unix_abs):
        # Windows 下以 / 开头但无盘符，视为相对路径
        if os.name == 'nt' and is_unix_abs and not path.drive:
            full_path = session_path / path_str.lstrip("/")
        else:
            full_path = path.resolve()

        try:
            if session_path in full_path.parents or full_path == session_path:
                parts = full_path.parts
                for i in range(len(parts) - 1):
                    # 修正连续重复的 session_name 嵌套
                    if parts[i] == session_name and parts[i + 1] == session_name:
                        return str(session_path / full_path.name)
                return str(full_path)
        except Exception:
            logger.error("解析路径出错")

        return str(full_path)

    else:
        parts = path.parts
        # 已含 session_name 或 output/ 前缀时，避免重复拼接
        if session_name in parts:
            return str(session_path / path.name)
        if parts and parts[0] == "output":
            return str(session_path / path.name)
        return str(session_path / path)


if __name__ == "__main__":
    session = "D:/project/output/session_abc"
    print(resolve_path("/workspace/报告.md", session))
    print(resolve_path("分析结果.md", session))
    print(resolve_path("output/session_abc/数据.md", session))