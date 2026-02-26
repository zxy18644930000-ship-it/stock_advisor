"""东方财富 A股要闻 + 财经导读"""

from datetime import datetime
from typing import List

from models import NewsItem
from news.base import BaseSource


class EastMoneySource(BaseSource):
    """东方财富网 — A股资讯"""

    name = "eastmoney"

    API = "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns"

    # A股要闻
    PARAMS_A_SHARE = {
        "columns": "298",
        "pageSize": "30",
        "pageIndex": "0",
        "param1": "",
        "param2": "",
    }

    # 财经导读
    PARAMS_FINANCE = {
        "columns": "297",
        "pageSize": "20",
        "pageIndex": "0",
        "param1": "",
        "param2": "",
    }

    async def fetch(self) -> List[NewsItem]:
        items: List[NewsItem] = []
        items.extend(await self._fetch_api(self.PARAMS_A_SHARE))
        items.extend(await self._fetch_api(self.PARAMS_FINANCE))
        return items

    async def _fetch_api(self, params: dict) -> List[NewsItem]:
        items = []
        try:
            resp = await self.client.get(self.API, params=params)
            data = resp.json()
            for entry in data.get("data", {}).get("list", []) or []:
                title = entry.get("title", "").strip()
                if not title:
                    continue

                pub_time = None
                date_str = entry.get("showTime") or entry.get("date", "")
                if date_str:
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                        try:
                            pub_time = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue

                art_code = entry.get("art_code", "") or entry.get("code", "")
                url = ""
                if art_code:
                    url = f"https://finance.eastmoney.com/a/{art_code}.html"

                items.append(NewsItem(
                    title=title,
                    url=url,
                    source=self.name,
                    content=entry.get("mediaName", ""),
                    publish_time=pub_time,
                ))
        except Exception:
            pass
        return items
