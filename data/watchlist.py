"""自选股行情 + 资金流向"""

import time

import pandas as pd
import requests

from config import WATCHLIST


_session = requests.Session()
_session.trust_env = False
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.sina.com.cn/",
})

_PUSH2_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
_PUSH2_FLOW_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"


def _code_to_secid(code: str) -> str:
    """股票代码转东方财富 secid (0.深 / 1.沪)"""
    if code.startswith(("6", "9")):
        return f"1.{code}"
    return f"0.{code}"


def fetch_watchlist() -> pd.DataFrame:
    """获取自选股实时行情 + 资金流向

    返回 DataFrame 含: 代码, 名称, 最新价, 涨跌幅, 涨跌额,
                       成交额, 换手率, 主力净流入, 主力净流入占比
    """
    if not WATCHLIST:
        return pd.DataFrame()

    secids = ",".join(_code_to_secid(c) for c in WATCHLIST)

    # 行情数据
    params = {
        "fltt": 2, "invt": 2,
        "fields": "f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f15,f16,f17,f18",
        "secids": secids,
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "_": int(time.time() * 1000),
    }
    r = _session.get(_PUSH2_URL, params=params, timeout=10)
    data = r.json()
    diffs = data.get("data", {}).get("diff", [])

    rows = {}
    for d in diffs:
        code = d.get("f12", "")
        rows[code] = {
            "代码": code,
            "名称": d.get("f14", ""),
            "最新价": d.get("f2", 0),
            "涨跌幅": d.get("f3", 0),
            "涨跌额": d.get("f4", 0),
            "成交量(手)": d.get("f5", 0),
            "成交额": d.get("f6", 0),
            "振幅": d.get("f7", 0),
            "换手率": d.get("f8", 0),
            "市盈率": d.get("f9", 0),
            "量比": d.get("f10", 0),
            "最高": d.get("f15", 0),
            "最低": d.get("f16", 0),
            "今开": d.get("f17", 0),
            "昨收": d.get("f18", 0),
        }

    time.sleep(0.3)

    # 资金流向数据
    params_flow = {
        "fltt": 2, "invt": 2,
        "fields": "f12,f14,f62,f184,f66,f69,f72,f75,f78,f81",
        "secids": secids,
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "_": int(time.time() * 1000),
    }
    try:
        r = _session.get(_PUSH2_FLOW_URL, params=params_flow, timeout=10)
        data = r.json()
        for d in data.get("data", {}).get("diff", []):
            code = d.get("f12", "")
            if code in rows:
                rows[code]["主力净流入"] = d.get("f62", 0)
                rows[code]["主力净流入占比"] = d.get("f184", 0)
                rows[code]["超大单净流入"] = d.get("f66", 0)
                rows[code]["大单净流入"] = d.get("f72", 0)
    except Exception:
        pass

    if not rows:
        return pd.DataFrame()

    # 保持 WATCHLIST 中的顺序
    ordered = [rows[c] for c in WATCHLIST if c in rows]
    return pd.DataFrame(ordered)
