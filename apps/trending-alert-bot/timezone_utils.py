"""北京时间工具模块"""

from datetime import datetime, timezone, timedelta

# 北京时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))


def beijing_now() -> datetime:
    """获取当前北京时间"""
    return datetime.now(BEIJING_TZ)


def beijing_today_start() -> datetime:
    """获取今天北京时间 00:00:00"""
    now = beijing_now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def format_beijing_time(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化当前北京时间"""
    return beijing_now().strftime(fmt)


def parse_time_to_beijing(time_str: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """解析时间字符串为北京时间（假设存储的时间都是北京时间）"""
    dt = datetime.strptime(time_str, fmt)
    return dt.replace(tzinfo=BEIJING_TZ)
