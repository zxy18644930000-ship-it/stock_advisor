"""并发新闻采集 + 去重"""

from __future__ import annotations

import asyncio
from typing import List, Optional

from models import NewsItem
from news.base import BaseSource
from news.eastmoney import EastMoneySource
from news.sina import SinaSource
from news.jin10 import Jin10Source


class NewsCollector:
    """A股新闻并发采集器"""

    def __init__(self, sources: Optional[List[BaseSource]] = None) -> None:
        self.sources = sources or [
            EastMoneySource(),
            SinaSource(),
            Jin10Source(),
        ]

    async def collect(self) -> List[NewsItem]:
        """并发采集 → 去重 → 按时间排序"""
        raw = await self._fetch_all()
        unique = self._deduplicate(raw)
        # 有时间的排前面，按时间降序
        unique.sort(
            key=lambda x: x.publish_time or __import__("datetime").datetime.min,
            reverse=True,
        )
        print(f"[新闻] 采集 {len(raw)} 条 -> 去重后 {len(unique)} 条")
        return unique

    async def _fetch_all(self) -> List[NewsItem]:
        tasks = [src.fetch() for src in self.sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_items: List[NewsItem] = []
        for i, result in enumerate(results):
            name = self.sources[i].name
            if isinstance(result, list):
                all_items.extend(result)
                print(f"  [{name}] {len(result)} 条")
            else:
                print(f"  [{name}] 采集失败: {result}")
        return all_items

    def _deduplicate(self, items: List[NewsItem]) -> List[NewsItem]:
        seen = set()
        unique = []
        for item in items:
            fp = item.fingerprint
            if fp not in seen:
                seen.add(fp)
                unique.append(item)
        return unique

    async def close(self) -> None:
        for src in self.sources:
            await src.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
