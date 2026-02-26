"""金十数据 — 7x24 实时财经快讯"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import List

from models import NewsItem
from news.base import BaseSource


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "")


class Jin10Source(BaseSource):
    """金十数据 — 快讯"""

    name = "jin10"

    FLASH_URL = "https://www.jin10.com/flash_newest.js"

    async def fetch(self) -> List[NewsItem]:
        return await self._fetch_flash()

    async def _fetch_flash(self) -> List[NewsItem]:
        items = []
        try:
            headers = {
                "Referer": "https://www.jin10.com/",
                "X-App-Id": "bVBF4FyRTn5NJF5n",
            }
            resp = await self.client.get(self.FLASH_URL, headers=headers)
            text = resp.text.strip()

            # 响应格式: var defined = [...]; 或纯 JSON
            if text.startswith("var "):
                match = re.search(r"\[.*\]", text, re.DOTALL)
                if match:
                    text = match.group()

            try:
                data = json.loads(text)
            except (json.JSONDecodeError, ValueError):
                return items

            for entry in data:
                content = entry.get("data", {})
                if isinstance(content, str):
                    title = content
                elif isinstance(content, dict):
                    title = content.get("content", "") or content.get("title", "")
                else:
                    continue

                title = _strip_html(title).strip()
                if not title or len(title) < 6:
                    continue

                pub_time = None
                time_str = entry.get("time")
                if time_str:
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                        try:
                            pub_time = datetime.strptime(time_str, fmt)
                            break
                        except ValueError:
                            continue

                is_important = entry.get("important", 0)
                prefix = "[重要] " if is_important else ""

                items.append(NewsItem(
                    title=prefix + title[:120],
                    url="https://www.jin10.com/",
                    source=self.name,
                    content=title[:200],
                    publish_time=pub_time,
                ))
        except Exception:
            pass
        return items[:40]
