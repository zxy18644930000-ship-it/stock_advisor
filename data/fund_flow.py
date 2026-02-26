"""资金流向 (AKShare / 新浪)

注意: 资金流接口依赖东方财富 push2 服务器，
从部分网络环境可能无法访问。失败时优雅降级。
"""

import time

import pandas as pd

from config import AKSHARE_INTERVAL, TOP_STOCK
from models import FundFlowReport


def fetch_fund_flow() -> FundFlowReport:
    """获取板块资金流 + 个股资金流排行"""
    report = FundFlowReport()

    try:
        import akshare as ak
    except ImportError:
        print("[资金] akshare 未安装，跳过资金流")
        return report

    # --- 板块资金流 ---
    print("[资金] 获取板块资金流排行...")
    try:
        sector = ak.stock_sector_fund_flow_rank(indicator="今日")
        time.sleep(AKSHARE_INTERVAL)
        report.sector_flow = sector.head(TOP_STOCK).reset_index(drop=True)
        print(f"  -> {len(sector)} 个板块")
    except Exception as e:
        print(f"  板块资金流获取失败(push2不可达): {e.__class__.__name__}")

    # --- 个股资金流 ---
    print("[资金] 获取个股资金流排行...")
    try:
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
        print(f"  -> {len(stock)} 只个股")
    except Exception as e:
        print(f"  个股资金流获取失败(push2不可达): {e.__class__.__name__}")

    return report
