"""数据模型定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import pandas as pd


@dataclass
class NewsItem:
    """单条新闻"""
    title: str
    url: str = ""
    source: str = ""
    content: str = ""
    publish_time: Optional[datetime] = None

    @property
    def fingerprint(self) -> str:
        return f"{self.source}:{self.title[:30]}"


@dataclass
class SectorReport:
    """板块行情摘要"""
    top_gainers: pd.DataFrame = field(default_factory=pd.DataFrame)   # 涨幅前N板块
    top_losers: pd.DataFrame = field(default_factory=pd.DataFrame)    # 跌幅前N板块
    concept_gainers: pd.DataFrame = field(default_factory=pd.DataFrame)
    concept_losers: pd.DataFrame = field(default_factory=pd.DataFrame)


@dataclass
class StockReport:
    """个股行情摘要"""
    top_gainers: pd.DataFrame = field(default_factory=pd.DataFrame)
    top_losers: pd.DataFrame = field(default_factory=pd.DataFrame)
    top_volume: pd.DataFrame = field(default_factory=pd.DataFrame)
    limit_up_count: int = 0
    limit_down_count: int = 0
    up_count: int = 0
    down_count: int = 0
    flat_count: int = 0


@dataclass
class FundFlowReport:
    """资金流向摘要"""
    sector_flow: pd.DataFrame = field(default_factory=pd.DataFrame)
    stock_inflow: pd.DataFrame = field(default_factory=pd.DataFrame)
    stock_outflow: pd.DataFrame = field(default_factory=pd.DataFrame)


@dataclass
class NewsReport:
    """新闻采集结果"""
    items: List[NewsItem] = field(default_factory=list)
    matched: dict = field(default_factory=dict)  # {板块名: [相关新闻]}


@dataclass
class MarketReport:
    """完整市场报告"""
    generated_at: datetime = field(default_factory=datetime.now)
    session: str = ""  # morning / afternoon
    sector: Optional[SectorReport] = None
    stock: Optional[StockReport] = None
    fund_flow: Optional[FundFlowReport] = None
    news: Optional[NewsReport] = None
