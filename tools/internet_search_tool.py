import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.tools import tool
from tavily import TavilyClient

from api.monitor import monitor
from utils.logger_utils import logger

load_dotenv()

_tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


@tool
def internet_search(
        query: str,
        topic: Literal["general", "news", "finance"] = "general",
        max_results: int = 5,
        include_raw_content: bool = False,
):
    """
    进行网络搜索，用于查询数据库和知识库之外的公开信息。

    :param query: 查询内容
    :param topic: 查询类别
    :param max_results: 返回条数
    :param include_raw_content: 是否返回原始详情
    """
    logger.debug(f"开始调用网络搜索工具，查询内容: {query}，查询数量: {max_results}")
    monitor.report_tool(
        tool_name="网络搜索工具",
        args={"query": query, "topic": topic, "max_results": max_results, "include_raw_content": include_raw_content},
    )
    return _tavily_client.search(
        query=query,
        topic=topic,
        max_results=max_results,
        include_raw_content=include_raw_content,
    )
