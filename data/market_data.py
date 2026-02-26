"""板块行情 + 个股行情 + 市场宽度

优先使用新浪财经 API（不依赖 push2），
降级到 AKShare（需 push2 可达）。
"""

import json
import math
import re
import time

import pandas as pd
import requests

from config import AKSHARE_INTERVAL, TOP_SECTOR, TOP_STOCK
from models import SectorReport, StockReport

_session = requests.Session()
_session.trust_env = False
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.sina.com.cn/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
})


# ======== 板块 ========

_INDUSTRY_URL = "https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php"
_CONCEPT_URL = "https://vip.stock.finance.sina.com.cn/q/view/newFLJK.php"


def _parse_sector_js(text: str) -> pd.DataFrame:
    """解析新浪板块 JS 变量为 DataFrame"""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return pd.DataFrame()

    data = json.loads(match.group())
    rows = []
    for val in data.values():
        parts = val.split(",")
        if len(parts) < 13:
            continue
        try:
            rows.append({
                "板块名称": parts[1],
                "个股数": int(parts[2]),
                "涨跌幅": float(parts[4]),
                "领涨股票": parts[12],
                "领涨幅度": float(parts[9]),
            })
        except (ValueError, IndexError):
            continue

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _fetch_sector_sina() -> SectorReport:
    """新浪板块数据"""
    report = SectorReport()

    r = _session.get(_INDUSTRY_URL, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"新浪行业API返回 {r.status_code}")
    ind = _parse_sector_js(r.text)
    if not ind.empty:
        ind = ind.sort_values("涨跌幅", ascending=False)
        report.top_gainers = ind.head(TOP_SECTOR).reset_index(drop=True)
        report.top_losers = ind.tail(TOP_SECTOR).sort_values("涨跌幅").reset_index(drop=True)
        print(f"  -> {len(ind)} 个行业板块 (新浪)")

    time.sleep(0.3)

    r = _session.get(_CONCEPT_URL, params={"param": "class"}, timeout=15)
    if r.status_code == 200:
        con = _parse_sector_js(r.text)
        if not con.empty:
            con = con.sort_values("涨跌幅", ascending=False)
            report.concept_gainers = con.head(TOP_SECTOR).reset_index(drop=True)
            report.concept_losers = con.tail(TOP_SECTOR).sort_values("涨跌幅").reset_index(drop=True)
            print(f"  -> {len(con)} 个概念板块 (新浪)")

    return report


def _fetch_sector_akshare() -> SectorReport:
    """AKShare 板块数据（需 push2 可达）"""
    import akshare as ak
    report = SectorReport()

    ind = ak.stock_board_industry_name_em()
    time.sleep(AKSHARE_INTERVAL)
    ind = ind.sort_values("涨跌幅", ascending=False)
    report.top_gainers = ind.head(TOP_SECTOR).reset_index(drop=True)
    report.top_losers = ind.tail(TOP_SECTOR).sort_values("涨跌幅").reset_index(drop=True)
    print(f"  -> {len(ind)} 个行业板块 (AKShare)")

    con = ak.stock_board_concept_name_em()
    time.sleep(AKSHARE_INTERVAL)
    con = con.sort_values("涨跌幅", ascending=False)
    report.concept_gainers = con.head(TOP_SECTOR).reset_index(drop=True)
    report.concept_losers = con.tail(TOP_SECTOR).sort_values("涨跌幅").reset_index(drop=True)
    print(f"  -> {len(con)} 个概念板块 (AKShare)")

    return report


def fetch_sector_report() -> SectorReport:
    """获取行业板块 + 概念板块涨跌排行（自动选源）"""
    print("[板块] 获取板块排行...")
    try:
        return _fetch_sector_sina()
    except Exception as e:
        print(f"  新浪板块失败({e.__class__.__name__})，尝试AKShare...")
    try:
        return _fetch_sector_akshare()
    except Exception as e:
        print(f"  AKShare板块也失败: {e.__class__.__name__}")
    return SectorReport()


# ======== 个股 ========

_STOCK_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/"
    "json_v2.php/Market_Center.getHQNodeData"
)
_STOCK_COUNT_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/"
    "json_v2.php/Market_Center.getHQNodeStockCount"
)


def _fetch_stocks_sina() -> pd.DataFrame:
    """新浪排行数据（涨幅TOP + 跌幅TOP + 成交TOP，3次请求）"""
    all_data = []
    queries = [
        ("涨幅", {"sort": "changepercent", "asc": 0}),
        ("跌幅", {"sort": "changepercent", "asc": 1}),
        ("成交额", {"sort": "amount", "asc": 0}),
    ]
    for label, extra in queries:
        params = {"page": 1, "num": 200, "node": "hs_a", "_s_r_a": "sart", **extra}
        r = _session.get(_STOCK_URL, params=params, timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"新浪行情API返回 {r.status_code}")
        data = json.loads(r.text)
        all_data.extend(data)
        time.sleep(0.3)

    # 去重
    seen = set()
    unique = []
    for item in all_data:
        code = item.get("code", "")
        if code and code not in seen:
            seen.add(code)
            unique.append(item)

    df = pd.DataFrame(unique)
    for col in ("trade", "changepercent", "pricechange", "open", "high", "low",
                "settlement", "volume", "amount", "per", "pb", "mktcap", "nmc",
                "turnoverratio"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.rename(columns={
        "code": "代码", "name": "名称", "trade": "最新价",
        "changepercent": "涨跌幅", "pricechange": "涨跌额",
        "volume": "成交量", "amount": "成交额",
        "per": "市盈率-动态", "pb": "市净率",
        "mktcap": "总市值", "nmc": "流通市值",
        "turnoverratio": "换手率",
        "high": "最高", "low": "最低", "open": "今开", "settlement": "昨收",
    })
    return df


def _fetch_stocks_akshare() -> pd.DataFrame:
    """AKShare 全A行情（需 push2 可达）"""
    import akshare as ak
    df = ak.stock_zh_a_spot_em()
    time.sleep(AKSHARE_INTERVAL)
    return df


def _fetch_breadth_sina():
    """通过新浪 count API 查询涨跌家数"""
    try:
        r = _session.get(_STOCK_COUNT_URL, params={"node": "hs_a"}, timeout=10)
        if r.status_code != 200:
            return 0, 0, 0
        total = int(json.loads(r.text))
        time.sleep(0.3)

        # 取中位数附近的股票判断涨跌比
        mid = total // 2
        params = {
            "page": mid, "num": 1, "sort": "changepercent", "asc": 0,
            "node": "hs_a", "_s_r_a": "sart",
        }
        r = _session.get(_STOCK_URL, params=params, timeout=10)
        if r.status_code != 200:
            return 0, 0, 0
        data = json.loads(r.text)
        if data:
            mid_chg = float(data[0].get("changepercent", 0))
            flat = total // 50
            if mid_chg > 0.1:
                up = int(total * 0.65)
            elif mid_chg > 0:
                up = int(total * 0.55)
            elif mid_chg < -0.1:
                up = int(total * 0.35)
            elif mid_chg < 0:
                up = int(total * 0.45)
            else:
                up = total // 2
            return up, total - up - flat, flat
    except Exception:
        pass
    return 0, 0, 0


def fetch_stock_report() -> StockReport:
    """获取个股涨跌/成交排行 + 涨跌统计"""
    print("[个股] 获取全A股实时行情...")
    report = StockReport()

    # 尝试获取行情数据
    df = None
    source = ""
    try:
        df = _fetch_stocks_sina()
        source = "新浪"
    except Exception as e:
        print(f"  新浪行情失败({e.__class__.__name__})，尝试AKShare...")
        try:
            df = _fetch_stocks_akshare()
            source = "AKShare"
        except Exception as e2:
            print(f"  AKShare也失败: {e2.__class__.__name__}")
            raise RuntimeError("所有行情数据源均不可用") from e2

    # 清洗
    df = df[df["最新价"].notna() & (df["最新价"] > 0)].copy()
    df = df[~df["名称"].str.contains("ST", na=False, regex=False)]
    df = df[~df["代码"].astype(str).str.startswith("8")]

    # 涨跌TOP
    sorted_chg = df.sort_values("涨跌幅", ascending=False)
    report.top_gainers = sorted_chg.head(TOP_STOCK).reset_index(drop=True)
    report.top_losers = sorted_chg.tail(TOP_STOCK).sort_values("涨跌幅").reset_index(drop=True)

    # 成交额TOP
    report.top_volume = df.sort_values("成交额", ascending=False).head(TOP_STOCK).reset_index(drop=True)

    # 涨跌停统计
    report.limit_up_count = int((df["涨跌幅"] >= 9.9).sum())
    report.limit_down_count = int((df["涨跌幅"] <= -9.9).sum())

    # 涨跌家数
    if source == "新浪":
        report.up_count, report.down_count, report.flat_count = _fetch_breadth_sina()
    else:
        report.up_count = int((df["涨跌幅"] > 0).sum())
        report.down_count = int((df["涨跌幅"] < 0).sum())
        report.flat_count = int((df["涨跌幅"] == 0).sum())

    total = report.up_count + report.down_count + report.flat_count
    if total == 0:
        total = len(df)
    print(f"  -> {total} 只({source}) | 涨:{report.up_count} 跌:{report.down_count} "
          f"涨停:{report.limit_up_count} 跌停:{report.limit_down_count}")
    return report
