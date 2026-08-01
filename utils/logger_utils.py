
import logging
import colorlog

# 初始化全局日志对象
logger = logging.getLogger()

# 设置日志的默认的级别
logger.setLevel(logging.DEBUG)

# 加载彩色日志处理器
handler = colorlog.StreamHandler()
# 定义日志输出的格式
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',  # INFO 显示为绿色
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red',
    }
))

# 应用日志配置信息
logger.addHandler(handler)


if __name__ == '__main__':
    logger.debug("工具开始执行")  # 青色
    logger.info("会话目录创建成功")  # 绿色
    logger.warning("文件路径存在风险")  # 黄色
    logger.error("WebSocket推送失败")  # 红色
    logger.critical("数据库连接崩溃")  # 加粗红色