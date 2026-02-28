"""资金流向 — 东方财富 push2 API（主力）+ AKShare（备用）

push2.eastmoney.com 提供实时资金流向排行数据。
"""

import time

import pandas as pd
import requests

from config import AKSHARE_INTERVAL, TOP_STOCK
from models import FundFlowReport


_session = requests.Session()
_session.trust_env = False
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://data.eastmoney.com/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
})

_PUSH2_URL = "https://push2.eastmoney.com/api/qt/clist/get"


# ───────── 东方财富 push2 API ─────────

def _push2_sector_flow() -> pd.DataFrame:
    """板块资金流向排行（按主力净流入降序）"""
    params = {
        "pn": 1, "pz": TOP_STOCK, "po": 1, "np": 1,
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fltt": 2, "invt": 2, "fid": "f62",
        "fs": "m:90+t:2",
        "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81",
        "_": int(time.time() * 1000),
    }
    r = _session.get(_PUSH2_URL, params=params, timeout=10)
    data = r.json()
    diffs = data.get("data", {}).get("diff", [])
    if not diffs:
        raise RuntimeError("push2 板块资金流无数据")

    rows = []
    for d in diffs:
        rows.append({
            "名称": d.get("f14", ""),
            "涨跌幅": d.get("f3", 0),
            "今日主力净流入-净额": d.get("f62", 0),
            "今日主力净流入-净占比": d.get("f184", 0),
            "今日超大单净流入-净额": d.get("f66", 0),
            "今日大单净流入-净额": d.get("f72", 0),
        })
    return pd.DataFrame(rows)


def _push2_stock_flow(ascending: bool = False, size: int = None) -> pd.DataFrame:
    """个股资金流排行
    ascending=False: 净流入TOP（降序）
    ascending=True:  净流出TOP（升序）
    """
    if size is None:
        size = TOP_STOCK
    params = {
        "pn": 1, "pz": size, "po": 0 if ascending else 1, "np": 1,
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fltt": 2, "invt": 2, "fid": "f62",
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
        "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81",
        "_": int(time.time() * 1000),
    }
    r = _session.get(_PUSH2_URL, params=params, timeout=10)
    data = r.json()
    diffs = data.get("data", {}).get("diff", [])
    if not diffs:
        raise RuntimeError("push2 个股资金流无数据")

    rows = []
    for d in diffs:
        rows.append({
            "代码": d.get("f12", ""),
            "名称": d.get("f14", ""),
            "最新价": d.get("f2", 0),
            "涨跌幅": d.get("f3", 0),
            "今日主力净流入-净额": d.get("f62", 0),
            "今日主力净流入-净占比": d.get("f184", 0),
            "今日超大单净流入-净额": d.get("f66", 0),
            "今日大单净流入-净额": d.get("f72", 0),
        })
    return pd.DataFrame(rows)


def _fetch_flow_push2() -> FundFlowReport:
    """使用 push2 API 获取资金流向"""
    report = FundFlowReport()

    print("[资金] 获取板块资金流排行...")
    try:
        report.sector_flow = _push2_sector_flow()
        print(f"  -> {len(report.sector_flow)} 个板块")
    except Exception as e:
        print(f"  板块资金流失败: {e}")

    time.sleep(0.3)

    print("[资金] 获取个股资金净流入 TOP...")
    try:
        report.stock_inflow = _push2_stock_flow(ascending=False)
        print(f"  -> {len(report.stock_inflow)} 只")
    except Exception as e:
        print(f"  个股净流入失败: {e}")

    time.sleep(0.3)

    print("[资金] 获取个股资金净流出 TOP...")
    try:
        report.stock_outflow = _push2_stock_flow(ascending=True)
        print(f"  -> {len(report.stock_outflow)} 只")
    except Exception as e:
        print(f"  个股净流出失败: {e}")

    return report


# ───────── AKShare 备选 ─────────

def _fetch_flow_akshare() -> FundFlowReport:
    """AKShare 资金流向"""
    import akshare as ak
    report = FundFlowReport()

    print("[资金] 获取板块资金流排行 (AKShare)...")
    sector = ak.stock_sector_fund_flow_rank(indicator="今日")
    time.sleep(AKSHARE_INTERVAL)
    report.sector_flow = sector.head(TOP_STOCK).reset_index(drop=True)

    print("[资金] 获取个股资金流排行 (AKShare)...")
    stock = ak.stock_individual_fund_flow_rank(indicator="今日")
    time.sleep(AKSHARE_INTERVAL)
    stock["今日主力净流入-净额"] = pd.to_numeric(
        stock["今日主力净流入-净额"], errors="coerce"
    )
    sorted_flow = stock.sort_values("今日主力净流入-净额", ascending=False)
    report.stock_inflow = sorted_flow.head(TOP_STOCK).reset_index(drop=True)
    report.stock_outflow = sorted_flow.tail(TOP_STOCK).sort_values(
        "今日主力净流入-净额"
    ).reset_index(drop=True)

    return report


# ───────── 对外接口 ─────────

def fetch_fund_flow() -> FundFlowReport:
    """获取板块资金流 + 个股资金流排行（自动选源）"""
    try:
        report = _fetch_flow_push2()
        if not report.sector_flow.empty or not report.stock_inflow.empty:
            return report
    except Exception as e:
        print(f"  push2资金流失败({e.__class__.__name__})")

    try:
        return _fetch_flow_akshare()
    except Exception as e:
        print(f"  AKShare资金流也失败: {e.__class__.__name__}")

    return FundFlowReport()
