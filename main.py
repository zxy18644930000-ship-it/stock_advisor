"""A股投资顾问 — CLI入口 + 定时调度"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime

# AKShare 通过 requests 访问国内站点；macOS 系统偏好设置可能配了代理，
# 导致 requests 自动走代理。这里 monkey-patch Session 禁用 trust_env。
import requests as _requests
_OrigSession = _requests.Session
class _NoProxySession(_OrigSession):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.trust_env = False
_requests.Session = _NoProxySession

from models import MarketReport, NewsReport
from data.market_data import fetch_sector_report, fetch_stock_report
from data.fund_flow import fetch_fund_flow
from data.watchlist import fetch_watchlist
from data.watch_sector import fetch_watch_sectors
from data.reasons import analyze_reasons
from news.collector import NewsCollector
from news.matcher import match_news_to_sectors, extract_sector_names
from report import terminal, markdown


def determine_session() -> str:
    """根据当前时间判断上午盘/下午盘"""
    hour = datetime.now().hour
    return "morning" if hour < 13 else "afternoon"


async def run_once(skip_news: bool = False) -> None:
    """执行一次完整的市场分析"""
    print("=" * 60)
    print(f"  A股投资顾问 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    report = MarketReport(
        generated_at=datetime.now(),
        session=determine_session(),
    )

    # 1. 核心行情数据（失败则退出）
    try:
        report.stock = fetch_stock_report()
    except Exception as e:
        print(f"\n[错误] 核心行情数据获取失败，无法生成报告: {e}")
        sys.exit(1)

    # 2. 板块数据（容错）
    try:
        report.sector = fetch_sector_report()
    except Exception as e:
        print(f"[警告] 板块数据获取失败: {e}")

    # 3. 资金流向（容错）
    try:
        report.fund_flow = fetch_fund_flow()
    except Exception as e:
        print(f"[警告] 资金流向获取失败: {e}")

    # 4. 自选股（容错）
    try:
        report.watchlist = fetch_watchlist()
        if report.watchlist is not None and not report.watchlist.empty:
            print(f"[自选] 获取到 {len(report.watchlist)} 只自选股行情")
    except Exception as e:
        print(f"[警告] 自选股数据获取失败: {e}")

    # 4.5 关注板块（容错）
    try:
        report.watch_sectors = fetch_watch_sectors()
    except Exception as e:
        print(f"[警告] 关注板块数据获取失败: {e}")

    # 5. 新闻采集（容错，可跳过）
    if not skip_news:
        try:
            async with NewsCollector() as collector:
                news_items = await collector.collect()

            # 关联匹配：新闻 ↔ 涨跌板块
            matched = {}
            if report.sector:
                sector_names = []
                sector_names.extend(extract_sector_names(report.sector.top_gainers))
                sector_names.extend(extract_sector_names(report.sector.top_losers))
                sector_names.extend(extract_sector_names(report.sector.concept_gainers))
                sector_names.extend(extract_sector_names(report.sector.concept_losers))
                if sector_names:
                    matched = match_news_to_sectors(news_items, sector_names)

            report.news = NewsReport(items=news_items, matched=matched)
        except Exception as e:
            print(f"[警告] 新闻采集失败: {e}")
    else:
        print("[跳过] 新闻采集 (--no-news)")

    # 6. 涨跌原因分析（容错）
    try:
        report.reasons = analyze_reasons(report)
    except Exception as e:
        print(f"[警告] 原因分析失败: {e}")

    # 7. 输出报告
    terminal.render(report)
    filepath = markdown.save(report)
    print(f"\n[保存] Markdown 报告: {filepath}")


def start_scheduler() -> None:
    """启动 APScheduler 定时任务"""
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from config import SCHEDULE_MORNING, SCHEDULE_AFTERNOON

    scheduler = BlockingScheduler()

    def job():
        asyncio.run(run_once())

    # 周一至周五 11:35
    scheduler.add_job(
        job,
        CronTrigger(
            day_of_week="mon-fri",
            hour=SCHEDULE_MORNING["hour"],
            minute=SCHEDULE_MORNING["minute"],
        ),
        id="morning",
        name="上午盘报告",
    )

    # 周一至周五 15:05
    scheduler.add_job(
        job,
        CronTrigger(
            day_of_week="mon-fri",
            hour=SCHEDULE_AFTERNOON["hour"],
            minute=SCHEDULE_AFTERNOON["minute"],
        ),
        id="afternoon",
        name="下午盘报告",
    )

    print("=" * 60)
    print("  A股投资顾问 — 定时调度已启动")
    print(f"  上午盘: 周一至周五 {SCHEDULE_MORNING['hour']}:{SCHEDULE_MORNING['minute']:02d}")
    print(f"  下午盘: 周一至周五 {SCHEDULE_AFTERNOON['hour']}:{SCHEDULE_AFTERNOON['minute']:02d}")
    print("  按 Ctrl+C 退出")
    print("=" * 60)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n调度已停止")


def _build_demo_report() -> MarketReport:
    """生成模拟数据报告，用于验证渲染流程"""
    import pandas as pd
    from models import (MarketReport, SectorReport, StockReport,
                        FundFlowReport, NewsReport, NewsItem)

    # 模拟板块数据
    sector_data = {
        "板块名称": ["半导体", "光伏设备", "汽车整车", "白酒", "房地产开发"],
        "涨跌幅": [3.25, 2.87, 2.15, 1.68, 1.23],
    }
    sector_data_down = {
        "板块名称": ["保险", "银行", "煤炭", "石油", "电力"],
        "涨跌幅": [-2.31, -1.87, -1.52, -1.15, -0.98],
    }

    # 模拟个股
    stock_cols = ["代码", "名称", "最新价", "涨跌幅", "成交额"]
    gain_data = [
        ["001234", "测试科技", 35.20, 19.98, 15.2e8],
        ["002345", "算力芯片", 88.50, 15.32, 28.5e8],
        ["003456", "光刻材料", 42.10, 12.05, 9.8e8],
    ]
    lose_data = [
        ["004567", "地产A", 5.20, -9.95, 3.2e8],
        ["005678", "保险B", 12.80, -7.32, 5.1e8],
        ["006789", "煤炭C", 8.90, -5.68, 2.3e8],
    ]

    # 模拟资金流
    fund_cols_sector = ["名称", "今日主力净流入-净额"]
    fund_sector = pd.DataFrame([
        ["半导体", 12.5e8], ["光伏", 8.3e8], ["汽车", 5.1e8],
    ], columns=fund_cols_sector)

    fund_cols_stock = ["代码", "名称", "今日主力净流入-净额"]
    fund_in = pd.DataFrame([
        ["001234", "测试科技", 3.2e8],
        ["002345", "算力芯片", 2.8e8],
    ], columns=fund_cols_stock)
    fund_out = pd.DataFrame([
        ["004567", "地产A", -2.1e8],
        ["005678", "保险B", -1.5e8],
    ], columns=fund_cols_stock)

    # 模拟新闻
    news_items = [
        NewsItem(title="国务院发布半导体产业扶持新政策", source="eastmoney",
                 publish_time=datetime.now()),
        NewsItem(title="光伏行业需求超预期 多家企业订单饱满", source="sina",
                 publish_time=datetime.now()),
        NewsItem(title="新能源汽车2月销量同比增长45%", source="jin10",
                 publish_time=datetime.now()),
        NewsItem(title="央行：继续实施稳健的货币政策", source="eastmoney",
                 publish_time=datetime.now()),
        NewsItem(title="A股三大指数集体收涨 两市成交额破万亿", source="sina",
                 publish_time=datetime.now()),
    ]

    return MarketReport(
        generated_at=datetime.now(),
        session=determine_session(),
        sector=SectorReport(
            top_gainers=pd.DataFrame(sector_data),
            top_losers=pd.DataFrame(sector_data_down),
            concept_gainers=pd.DataFrame(sector_data),
            concept_losers=pd.DataFrame(sector_data_down),
        ),
        stock=StockReport(
            top_gainers=pd.DataFrame(gain_data, columns=stock_cols),
            top_losers=pd.DataFrame(lose_data, columns=stock_cols),
            top_volume=pd.DataFrame(gain_data, columns=stock_cols),
            limit_up_count=42, limit_down_count=8,
            up_count=3200, down_count=1800, flat_count=150,
        ),
        fund_flow=FundFlowReport(
            sector_flow=fund_sector,
            stock_inflow=fund_in,
            stock_outflow=fund_out,
        ),
        news=NewsReport(
            items=news_items,
            matched={"半导体": [news_items[0]], "光伏设备": [news_items[1]],
                     "汽车整车": [news_items[2]]},
        ),
    )


def start_web(port: int = 8088) -> None:
    """在后台线程启动 Web 前端"""
    import threading
    from web import app

    def _run():
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    print(f"  Web 前端: http://localhost:{port}")


def main():
    parser = argparse.ArgumentParser(description="A股每日投资顾问")
    parser.add_argument("--schedule", action="store_true", help="启动定时调度 (11:35, 15:05 周一至周五)")
    parser.add_argument("--web", action="store_true", help="启动 Web 前端 (默认端口 8088)")
    parser.add_argument("--port", type=int, default=8088, help="Web 前端端口 (默认 8088)")
    parser.add_argument("--no-news", action="store_true", help="跳过新闻采集 (快速模式)")
    parser.add_argument("--demo", action="store_true", help="使用模拟数据验证报告渲染")
    args = parser.parse_args()

    if args.demo:
        report = _build_demo_report()
        terminal.render(report)
        filepath = markdown.save(report)
        print(f"\n[保存] Markdown 报告: {filepath}")
    elif args.schedule:
        if args.web:
            start_web(args.port)
        start_scheduler()
    elif args.web:
        # 单独启动 Web 前端（不做定时调度）
        from web import app
        print(f"A股投资顾问 Web 前端: http://localhost:{args.port}")
        app.run(host="0.0.0.0", port=args.port, debug=False)
    else:
        asyncio.run(run_once(skip_news=args.no_news))


if __name__ == "__main__":
    main()
