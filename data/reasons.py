"""涨跌原因分析 — 综合新闻匹配 + 行业关联 + 涨停数据"""

import time
from typing import Dict, List, Optional

import pandas as pd
import requests

from models import MarketReport, NewsItem

_session = requests.Session()
_session.trust_env = False
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://data.eastmoney.com/",
})


# ─────────── 个股所属板块查询 ───────────

def _get_stock_sectors(codes: list) -> Dict[str, dict]:
    """获取个股所属行业和关键词

    使用两个数据源:
    1. datacenter-web 批量API (EM2016行业分类 → 关键词)
    2. F10公司概况API (sshy → 精确EM板块名)

    返回: {代码: {"行业": "光伏设备", "概念": ["电气设备","电源设备","太阳能"]}}
    """
    if not codes:
        return {}

    result = {}
    codes = [str(c) for c in codes]

    # ── 第1步: datacenter-web 批量获取 EM2016 行业分类 ──
    try:
        filter_str = '(SECURITY_CODE in ("' + '","'.join(codes) + '"))'
        r = _session.get(
            "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params={
                "reportName": "RPT_F10_BASIC_ORGINFO",
                "columns": "SECURITY_CODE,SECURITY_NAME_ABBR,EM2016",
                "filter": filter_str,
                "pageSize": 50, "pageNumber": 1,
            }, timeout=10,
        )
        data = r.json()
        if data.get("result") and data["result"].get("data"):
            for item in data["result"]["data"]:
                code = str(item.get("SECURITY_CODE", ""))
                em2016 = item.get("EM2016", "") or ""
                # EM2016 格式: "电气设备-电源设备-太阳能"
                keywords = [k.strip() for k in em2016.split("-") if k.strip()]
                industry = keywords[-1] if keywords else ""
                result[code] = {"行业": industry, "概念": keywords}
    except Exception:
        pass

    # ── 第2步: F10 API 获取精确的 EM 板块名 (sshy) ──
    for code in codes[:30]:  # 限30只
        try:
            exchange = "SH" if str(code).startswith(("6", "9")) else "SZ"
            r = _session.get(
                "https://emweb.securities.eastmoney.com/PC_HSF10/"
                "CompanySurvey/CompanySurveyAjax",
                params={"code": f"{exchange}{code}"}, timeout=8,
            )
            jbzl = r.json().get("jbzl", {})
            sshy = jbzl.get("sshy", "")
            if sshy:
                if code in result:
                    result[code]["行业"] = sshy
                else:
                    result[code] = {"行业": sshy, "概念": []}
            time.sleep(0.15)
        except Exception:
            continue

    return result


# ─────────── 涨停原因 ───────────

def _get_zt_reasons(date_str: str) -> Dict[str, dict]:
    """获取涨停池数据: {代码: {"行业": ..., "连板": N}}"""
    result = {}
    try:
        import akshare as ak
        df = ak.stock_zt_pool_em(date=date_str)
        for _, row in df.iterrows():
            code = str(row.get("代码", ""))
            result[code] = {
                "行业": row.get("所属行业", ""),
                "连板": int(row.get("连板数", 1)),
            }
    except Exception:
        pass
    return result


# ─────────── 新闻关键词匹配 ───────────

def _extract_reason_from_title(title: str, max_len: int = 18) -> str:
    """从新闻标题中提取简短原因"""
    # 去掉来源前缀
    for prefix in ("【", "金十数据", "[重要]"):
        if title.startswith(prefix):
            title = title.lstrip("【[重要] ")
    # 去掉尾部时间
    title = title.rstrip("）) ")
    if len(title) > max_len:
        title = title[:max_len] + "…"
    return title


def _match_news_to_name(name: str, news_items: List[NewsItem]) -> Optional[str]:
    """在新闻标题中搜索股票/板块名称，返回最相关的一条标题摘要"""
    if not name or not news_items:
        return None

    # 直接匹配名称
    for item in news_items:
        if name in item.title:
            return _extract_reason_from_title(item.title)

    # 尝试去掉常见后缀再匹配
    for suffix in ("股份", "科技", "集团", "电子", "新能", "智能"):
        short = name.replace(suffix, "")
        if len(short) >= 2:
            for item in news_items:
                if short in item.title:
                    return _extract_reason_from_title(item.title)

    return None


def _match_news_keywords(keywords: list, news_items: List[NewsItem]) -> Optional[str]:
    """用关键词列表在新闻中搜索匹配"""
    if not keywords or not news_items:
        return None
    for kw in keywords:
        if not kw or len(kw) < 2:
            continue
        for item in news_items:
            if kw in item.title:
                return _extract_reason_from_title(item.title)
    return None


# ─────────── 主接口 ───────────

def analyze_reasons(report: MarketReport) -> Dict[str, str]:
    """分析涨跌原因

    返回: {
        "stock:300274": "光伏设备板块走强; 概念:太阳能/储能",
        "sector:有色金属": "稀土价格上涨预期...",
        ...
    }
    """
    reasons = {}
    news_items = report.news.items if report.news else []
    date_str = report.generated_at.strftime("%Y%m%d")

    # 1. 获取涨停原因
    print("[原因] 获取涨停池数据...")
    zt_data = _get_zt_reasons(date_str)
    if zt_data:
        print(f"  -> {len(zt_data)} 只涨停股")

    # 2. 收集需要查询行业的个股代码
    stock_codes = set()
    if report.stock:
        for df in [report.stock.top_gainers, report.stock.top_losers, report.stock.top_volume]:
            if df is not None and not df.empty and "代码" in df.columns:
                stock_codes.update(df["代码"].astype(str).tolist())
    # 也把资金流向TOP的个股加入
    if report.fund_flow:
        for df in [report.fund_flow.stock_inflow, report.fund_flow.stock_outflow]:
            if df is not None and not df.empty and "代码" in df.columns:
                stock_codes.update(df["代码"].astype(str).tolist())

    # 3. 批量获取个股所属行业/概念
    print(f"[原因] 查询 {len(stock_codes)} 只个股的行业/概念...")
    stock_info = _get_stock_sectors(list(stock_codes)[:50])  # 限50只
    print(f"  -> 获取到 {len(stock_info)} 只")

    # 4. 为板块生成原因 (新闻匹配)
    # 板块名 -> 搜索关键词映射
    _sector_keywords = {
        "有色金属": ["有色", "稀土", "金属", "铜", "铝", "锂"],
        "煤炭行业": ["煤炭", "煤价", "动力煤"],
        "酿酒行业": ["白酒", "酿酒", "茅台"],
        "电子器件": ["芯片", "半导体", "电子"],
        "飞机制造": ["航空", "飞机", "军工"],
        "机械行业": ["机械", "装备", "制造"],
        "发电设备": ["电力", "发电", "电网", "特高压"],
        "农药化肥": ["农药", "化肥", "农业"],
        "陶瓷行业": ["陶瓷", "建材"],
        "开发区": ["开发区", "园区"],
    }
    if report.sector:
        for df in [report.sector.top_gainers, report.sector.top_losers,
                    report.sector.concept_gainers, report.sector.concept_losers]:
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                name = row.get("板块名称", "")
                if not name:
                    continue
                key = f"sector:{name}"
                if key in reasons:
                    continue
                # 从已匹配的新闻里找
                if report.news and report.news.matched and name in report.news.matched:
                    items = report.news.matched[name]
                    if items:
                        reasons[key] = _extract_reason_from_title(items[0].title)
                        continue
                # 直接在新闻中搜索板块名
                matched = _match_news_to_name(name, news_items)
                if matched:
                    reasons[key] = matched
                    continue
                # 用板块关键词搜索新闻
                keywords = _sector_keywords.get(name, [name])
                matched = _match_news_keywords(keywords, news_items)
                if matched:
                    reasons[key] = matched

    # 5. 为个股生成原因
    stock_dfs = []
    if report.stock:
        stock_dfs.extend([report.stock.top_gainers, report.stock.top_losers])
    if report.fund_flow:
        stock_dfs.extend([report.fund_flow.stock_inflow, report.fund_flow.stock_outflow])
    if stock_dfs:
        for df in stock_dfs:
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                code = str(row.get("代码", ""))
                name = str(row.get("名称", ""))
                chg = row.get("涨跌幅", 0)
                key = f"stock:{code}"
                if key in reasons:
                    continue

                parts = []

                # 涨停原因
                if code in zt_data:
                    zt = zt_data[code]
                    boards = zt.get("连板", 1)
                    industry = zt.get("行业", "")
                    if boards > 1:
                        parts.append(f"{boards}连板")
                    if industry:
                        parts.append(industry)

                # 行业/概念
                if code in stock_info:
                    info = stock_info[code]
                    industry = info.get("行业", "")
                    concepts = info.get("概念", [])

                    # 检查所属行业是否在涨跌板块TOP中
                    if industry and not parts:
                        # 看行业是否在板块涨跌榜
                        if report.sector:
                            for sec_df in [report.sector.top_gainers, report.sector.top_losers,
                                           report.sector.concept_gainers, report.sector.concept_losers]:
                                if sec_df is not None and not sec_df.empty:
                                    sector_names = sec_df["板块名称"].tolist() if "板块名称" in sec_df.columns else []
                                    if industry in sector_names:
                                        if chg and chg > 0:
                                            parts.append(f"{industry}板块走强")
                                        else:
                                            parts.append(f"{industry}板块走弱")
                                        break

                        if not parts and industry:
                            parts.append(industry)

                    # 匹配概念到新闻
                    if concepts and news_items:
                        news_match = _match_news_keywords(concepts[:5], news_items)
                        if news_match:
                            parts.append(news_match)

                # 新闻直接匹配股票名
                if not parts or (len(parts) == 1 and len(parts[0]) < 6):
                    news_match = _match_news_to_name(name, news_items)
                    if news_match:
                        parts.append(news_match)

                if parts:
                    reasons[key] = "; ".join(parts[:2])[:30]

    print(f"[原因] 共生成 {len(reasons)} 条原因")
    return reasons
