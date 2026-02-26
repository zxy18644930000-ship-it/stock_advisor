"""新浪财经 股票频道"""

from datetime import datetime
from typing import List

from models import NewsItem
from news.base import BaseSource


class SinaSource(BaseSource):
    """新浪财经 — 股票频道"""

    name = "sina"

    ROLL_URL = "https://feed.mix.sina.com.cn/api/roll/get"
    ROLL_PARAMS = {
        "pageid": "155",
        "lid": "2516",       # 股票频道
        "num": "30",
        "page": "1",
    }

    async def fetch(self) -> List[NewsItem]:
        return await self._fetch_roll_api()

    async def _fetch_roll_api(self) -> List[NewsItem]:
        items = []
        try:
            resp = await self.client.get(self.ROLL_URL, params=self.ROLL_PARAMS)
            data = resp.json()
            for entry in data.get("result", {}).get("data", []):
                title = entry.get("title", "").strip()
                if not title:
                    continue

                pub_time = None
                pub_ts = entry.get("ctime", "")
                if pub_ts:
                    try:
                        pub_time = datetime.fromtimestamp(int(pub_ts))
                    except (ValueError, OSError):
                        pass

                items.append(NewsItem(
                    title=title,
                    url=entry.get("url", ""),
                    source=self.name,
                    content=entry.get("intro", ""),
                    publish_time=pub_time,
                ))
        except Exception:
            pass
        return items
