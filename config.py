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
