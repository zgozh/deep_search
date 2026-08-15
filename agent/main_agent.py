import shutil
from pathlib import Path

from deepagents import create_deep_agent
from langchain_core.messages import AIMessage

from agent.llm import model
from agent.load_prompt import main_config
from agent.sub_agents.internet_sub_agent import internet_sub_agent
from agent.sub_agents.db_sub_agent import db_sub_agent
from agent.sub_agents.rag_sub_agent import rag_sub_agent
from api.context import set_session_context, reset_session_context, set_thread_context
from api.monitor import monitor
from tools.markdown_tools import generate_markdown
from tools.pdf_tools import convert_md_to_pdf
from tools.upload_file_read_tool import read_file_content
from utils.logger_utils import logger

# 主智能体：编排三个子智能体，并持有文件生成工具
main_agent = create_deep_agent(
    model=model,
    tools=[generate_markdown, convert_md_to_pdf, read_file_content],
    subagents=[internet_sub_agent, db_sub_agent, rag_sub_agent],
    system_prompt=main_config['system_prompt'],
)

project_root = Path(__file__).parents[1].resolve()


def _prepare_session_environment(thread_id: str):
    """
    初始化会话工作环境，返回 (会话目录绝对路径, 相对路径, 上传文件提示词)。

    - 创建 output/session_{thread_id} 目录作为隔离的工作空间
    - 将 upload/session_{thread_id} 下的上传文件复制进来
    - 路径统一转 POSIX 风格，避免模型对反斜杠产生歧义
    """
    session_dir = project_root / "output" / f"session_{thread_id}"
    session_dir.mkdir(parents=True, exist_ok=True)

    session_dir_str = str(session_dir).replace("\\", "/")
    relative_session_dir = str(session_dir.relative_to(project_root)).replace("\\", "/")

    upload_dir = project_root / "upload" / f"session_{thread_id}"
    uploaded_info = ""

    if upload_dir.exists():
        files = [f.name for f in upload_dir.iterdir() if f.is_file()]
        for f in files:
            shutil.copy2(upload_dir / f, session_dir / f)
        if files:
            uploaded_info = (
                "\n    [已上传文件] 已加载到工作目录:\n"
                + "\n".join(f"    - {f}" for f in files)
                + "\n    请优先使用工具读取并参考这些文件。"
            )

    return session_dir_str, relative_session_dir, uploaded_info


def _process_stream_chunk(chunk):
    """
    解析 LangGraph 流式输出的增量状态，并把关键事件上报前端：
    - tool_calls 中的 'task' 工具 → 上报子智能体委派事件
    - 无工具调用的 content → 上报最终回复
    """
    for node_name, state in chunk.items():
        if not state or "messages" not in state:
            continue
        messages = state["messages"]
        if not isinstance(messages, list) or not messages:
            continue

        last_msg = messages[-1]
        if isinstance(last_msg, AIMessage):
            if last_msg.tool_calls:
                for tool in last_msg.tool_calls:
                    if tool['name'] == 'task':
                        monitor.report_assistant(
                            tool['args'].get('subagent_type', 'Agent'),
                            {"desc": tool['args'].get('description')},
                        )
            elif last_msg.content:
                monitor.report_task_result(last_msg.content)


async def run_deep_agent(query: str, thread_id: str):
    """执行一次智能体任务，流式上报进度，返回 "Done" 或错误信息。"""
    session_dir_str, relative_session_dir, uploaded_info = _prepare_session_environment(thread_id)

    thread_token = set_thread_context(thread_id)
    session_token = set_session_context(session_dir_str)
    monitor.report_session_dir(path=session_dir_str)

    path_instruction = f"""
        【工作环境指令】
        工作目录: {relative_session_dir}
        {uploaded_info}

        规则：
        1. 新生成文件必须保存到工作目录：'{relative_session_dir}/filename'
        2. 读取已上传的文件时，请直接将文件名（例如：'开篇.txt'）作为 filename 参数传入（read_file_content）读取工具，不要带上任何目录前缀。
        3. 使用相对路径，禁止使用绝对路径
        4. 若存在上传文件，请先分析内容
        """

    try:
        async for chunk in main_agent.astream(
            {"messages": [{"role": "user", "content": f"问题:{query}, 额外描述:{path_instruction}"}]}
        ):
            _process_stream_chunk(chunk)
        return "Done"
    except Exception as e:
        logger.error(f"Error: {e}")
        monitor._emit("error", f"Execution failed: {e}")
        return f"Error: {e}"
    finally:
        reset_session_context(session_token, thread_token)


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_deep_agent("查询数据库中的药品信息，生成一个 PDF 文件。", "local_test"))
