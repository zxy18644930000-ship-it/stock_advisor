"""关注板块 — 获取指定板块的整体表现 + 成分股明细"""

import time

import pandas as pd
import requests

from config import WATCH_SECTORS


_session = requests.Session()
_session.trust_env = False
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://data.eastmoney.com/",
})

_PUSH2_URL = "https://push2.eastmoney.com/api/qt/clist/get"


def _fetch_sector_overview(bk_code: str) -> dict:
    """获取板块整体行情 (涨跌幅、成交额、资金流)"""
    # 直接用板块代码查询，fs=b:BKxxxx+f:!50
    params = {
        "pn": 1, "pz": 1, "po": 1, "np": 1,
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fltt": 2, "invt": 2, "fid": "f3",
        "fs": f"b:{bk_code}+f:!50",
        "fields": "f12,f14,f2,f3,f4,f6,f62,f184",
        "_": int(time.time() * 1000),
    }
    r = _session.get(_PUSH2_URL, params=params, timeout=10)
    data = r.json()
    # 从板块全量列表中按代码匹配
    total_amount = data.get("data", {}).get("total", 0)

    # 用另一个接口获取板块自身行情
    quote_url = "https://push2.eastmoney.com/api/qt/stock/get"
    secid = f"90.{bk_code}"
    params2 = {
        "secid": secid,
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fltt": 2, "invt": 2,
        "fields": "f43,f44,f45,f46,f47,f48,f50,f57,f58,f107,f162,f168,f169,f170,f171,f177,f47,f48",
        "_": int(time.time() * 1000),
    }
    r2 = _session.get(quote_url, params=params2, timeout=10)
    d = r2.json().get("data", {})
    return {
        "涨跌幅": d.get("f170", 0),
        "涨跌额": d.get("f169", 0),
        "成交额": d.get("f48", 0),
        "主力净流入": 0,
        "主力净流入占比": 0,
    }


def _fetch_sector_stocks(bk_code: str) -> pd.DataFrame:
    """获取板块成分股行情（按涨幅降序）"""
    params = {
        "pn": 1, "pz": 100, "po": 1, "np": 1,
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fltt": 2, "invt": 2, "fid": "f3",
        "fs": f"b:{bk_code}",
        "fields": "f12,f14,f2,f3,f4,f6,f7,f8,f62,f184",
        "_": int(time.time() * 1000),
    }
    r = _session.get(_PUSH2_URL, params=params, timeout=10)
    data = r.json()
    diffs = data.get("data", {}).get("diff", [])
    if not diffs:
        return pd.DataFrame()

    rows = []
    for d in diffs:
        rows.append({
            "代码": d.get("f12", ""),
            "名称": d.get("f14", ""),
            "最新价": d.get("f2", 0),
            "涨跌幅": d.get("f3", 0),
            "涨跌额": d.get("f4", 0),
            "成交额": d.get("f6", 0),
            "振幅": d.get("f7", 0),
            "换手率": d.get("f8", 0),
            "主力净流入": d.get("f62", 0),
            "主力净流入占比": d.get("f184", 0),
        })
    return pd.DataFrame(rows)


def fetch_watch_sectors() -> list:
    """获取所有关注板块的数据

    返回: [{"name": "证券", "code": "BK0473", "overview": {...}, "stocks": DataFrame}, ...]
    """
    if not WATCH_SECTORS:
        return []

    results = []
    for bk_code, name in WATCH_SECTORS.items():
        print(f"[板块关注] 获取 {name}({bk_code}) ...")
        try:
            overview = _fetch_sector_overview(bk_code)
            time.sleep(0.3)
            stocks = _fetch_sector_stocks(bk_code)
            time.sleep(0.3)

            # 板块整体资金流 = 成分股资金流之和
            if not stocks.empty and "主力净流入" in stocks.columns:
                total_flow = stocks["主力净流入"].sum()
                overview["主力净流入"] = total_flow

            # 统计
            up_count = int((stocks["涨跌幅"] > 0).sum()) if not stocks.empty else 0
            down_count = int((stocks["涨跌幅"] < 0).sum()) if not stocks.empty else 0
            flat_count = int((stocks["涨跌幅"] == 0).sum()) if not stocks.empty else 0
            limit_up = int((stocks["涨跌幅"] >= 9.9).sum()) if not stocks.empty else 0

            overview["上涨"] = up_count
            overview["下跌"] = down_count
            overview["平盘"] = flat_count
            overview["涨停"] = limit_up
            overview["总数"] = len(stocks)

            print(f"  -> {len(stocks)} 只成分股 | 涨:{up_count} 跌:{down_count} 涨停:{limit_up}")

            results.append({
                "name": name,
                "code": bk_code,
                "overview": overview,
                "stocks": stocks,
            })
        except Exception as e:
            print(f"  {name} 获取失败: {e}")

    return results
