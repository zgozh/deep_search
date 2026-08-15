import os

from dotenv import load_dotenv
from langchain_core.tools import tool
from ragflow_sdk import RAGFlow

from api.monitor import monitor

load_dotenv()

_ragflow_client = RAGFlow(
    api_key=os.getenv("RAGFLOW_API_KEY"),
    base_url=os.getenv("RAGFLOW_API_URL"),
)


@tool
def get_assistant_list() -> str:
    """
    获取 RAGFlow 中所有聊天助手及其关联知识库，返回格式：
    「助手名称:xxx , 描述: xx , 关联的知识库: x,x,x」每行一个。
    """
    monitor.report_tool(tool_name="查询ragflow助手列表信息")
    try:
        chat_list = _ragflow_client.list_chats()
        if not chat_list:
            return "未找到可用任何助手"

        lines = []
        for chat in chat_list:
            dataset_name_list = [dataset['name'] for dataset in chat.datasets]
            lines.append(
                f"助手名称:{chat.name} , 描述: {chat.description} , "
                f"关联的知识库: {','.join(dataset_name_list)}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"查询助手列表失败：{str(e)}"


@tool
def create_ask_delete(chat_name: str, question: str) -> str:
    """
    向指定名称的助手提问并返回答案（临时会话，问完即删）。

    :param chat_name: 助手名称，需先通过 get_assistant_list 确认
    :param question: 本次提问的问题
    """
    monitor.report_tool(tool_name="向ragflow提问工具", args={"chat_name": chat_name})
    try:
        list_chats = _ragflow_client.list_chats(name=chat_name)
        if not list_chats:
            return f"未找到名称为{chat_name}的助手"

        chat = list_chats[0]
        session = chat.create_session(name="temp_session")
        stream = session.ask(question=question, stream=True)

        final_result = ""
        for chunk in stream:
            # 流式 chunk 是累加的，取最后一个即可
            final_result = chunk.content

        chat.delete_sessions([session.id])
        return final_result
    except Exception as e:
        return f"向{chat_name}提问失败：{str(e)}"


if __name__ == "__main__":
    print(get_assistant_list.invoke({}))
