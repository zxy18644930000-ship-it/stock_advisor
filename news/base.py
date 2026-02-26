"""异步新闻源基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

import httpx

from config import HEADERS, REQUEST_TIMEOUT
from models import NewsItem


class BaseSource(ABC):
    """所有新闻源的抽象基类"""

    name: str = "base"

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            proxy=None,  # 国内站点不走代理
        )

    async def close(self) -> None:
        await self.client.aclose()

    @abstractmethod
    async def fetch(self) -> List[NewsItem]:
        """采集新闻列表，子类必须实现"""
        ...

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
