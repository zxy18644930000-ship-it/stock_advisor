"""A股投资顾问 — 全局配置"""

# HTTP 请求头
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 新闻采集超时(秒)
REQUEST_TIMEOUT = 15

# AKShare 调用间隔(秒) — 防限速
AKSHARE_INTERVAL = 0.3

# 报告输出目录
OUTPUT_DIR = "output"

# 板块 / 个股 TOP N
TOP_SECTOR = 5
TOP_STOCK = 10

# 定时调度 (周一至周五)
SCHEDULE_MORNING = {"hour": 11, "minute": 35}
SCHEDULE_AFTERNOON = {"hour": 15, "minute": 5}

# 自选股 — {代码: 名称}
# 关注板块 — {板块代码: 板块名称}
# 板块代码可在东方财富行业板块页面查到，格式为 BKxxxx
WATCH_SECTORS = {
    "BK0473": "证券",
}

# 自选股 — {代码: 名称}
WATCHLIST = {
    "300274": "阳光电源",
    "600683": "京投发展",
    "300749": "顶固集创",
}
