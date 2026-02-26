"""新闻 ↔ 板块/个股 关联匹配 (jieba)"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

import jieba
import pandas as pd

from models import NewsItem


def match_news_to_sectors(
    news_items: List[NewsItem],
    sector_names: List[str],
) -> Dict[str, List[NewsItem]]:
    """
    将新闻标题/内容与板块名称做关键词匹配。

    Returns:
        {板块名: [匹配到的 NewsItem, ...]}
    """
    if not news_items or not sector_names:
        return {}

    result: Dict[str, List[NewsItem]] = defaultdict(list)

    # 将板块名加入 jieba 词典以提升切分准确率
    for name in sector_names:
        jieba.add_word(name)

    for item in news_items:
        text = item.title + " " + item.content
        words = set(jieba.lcut(text))
        for sector in sector_names:
            # 板块名直接出现在文本中，或板块名被切出
            if sector in text or sector in words:
                result[sector].append(item)

    return dict(result)


def extract_sector_names(sector_df: pd.DataFrame) -> List[str]:
    """从板块 DataFrame 提取板块名称列表"""
    if sector_df is None or sector_df.empty:
        return []
    col = "板块名称" if "板块名称" in sector_df.columns else sector_df.columns[1]
    return sector_df[col].dropna().tolist()
