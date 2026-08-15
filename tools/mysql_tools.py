import os
from dotenv import load_dotenv
from api.monitor import monitor
from mysql.connector import connect, Error
from langchain_core.tools import tool

load_dotenv()


def get_db_config():
    """从环境变量读取数据库连接配置，缺失核心项时直接报错。"""
    config = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "database": os.getenv("MYSQL_DATABASE"),
        "charset": os.getenv("MYSQL_CHARSET", "utf8mb4"),
        "collation": os.getenv("MYSQL_COLLATION", "utf8mb4_unicode_ci"),
        "autocommit": True,
        "sql_mode": os.getenv("MYSQL_SQL_MODE", "TRADITIONAL")
    }
    config = {k: v for k, v in config.items() if v is not None}

    required_keys = ["user", "password", "database"]
    missing_keys = [k for k in required_keys if k not in config]
    if missing_keys:
        raise ValueError(f"缺失数据库核心配置：{', '.join(missing_keys)}")
    return config


def _rows_to_table(description, rows) -> str:
    """把查询结果（列描述 + 行数据）拼成逗号分隔的表格文本，便于模型理解。"""
    if not description:
        return None
    header = ",".join(col[0] for col in description)
    body = "\n".join(",".join(map(str, row)) for row in rows)
    return f"{header}\n{body}"


@tool
def list_sql_tables() -> str:
    """
    列出当前数据库中的全部表名。
    """
    monitor.report_tool(tool_name="搜索表名工具")
    try:
        with connect(**get_db_config()) as conn:
            with conn.cursor() as cursor:
                cursor.execute("show tables;")
                rows = cursor.fetchall()
                if not rows:
                    return "没有可用表"
                table_names = [item[0] for item in rows]
                return f"可用表:{','.join(table_names)}"
    except Error as e:
        return "数据库连接失败: " + str(e)


@tool
def get_table_data(table_name: str) -> str:
    """
    读取指定表的前 100 行数据，返回逗号分隔的表格文本：
    第一行是列名，之后每行是一条记录。
    """
    monitor.report_tool(tool_name="搜索指定表名的数据工具", args={"table_name": table_name})
    try:
        with connect(**get_db_config()) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"select * from {table_name} limit 100;")
                table = _rows_to_table(cursor.description, cursor.fetchall())
                return table if table is not None else f"当前表 {table_name} 没有数据"
    except Error as e:
        return "数据库连接失败: " + str(e)


@tool
def execute_sql_query(sql: str) -> str:
    """
    执行自定义 SQL 查询，返回逗号分隔的表格文本。
    """
    monitor.report_tool(tool_name="执行自定义SQL查询工具", args={"sql": sql})
    try:
        with connect(**get_db_config()) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                table = _rows_to_table(cursor.description, cursor.fetchall())
                return table if table is not None else f"当前语句 {sql} 没有数据"
    except Error as e:
        return "数据库连接失败: " + str(e)


if __name__ == "__main__":
    print(list_sql_tables.invoke({}))
    print(get_table_data.invoke({"table_name": "drugs"}))
    print(execute_sql_query.invoke({"sql": "select * from drugs limit 100"}))