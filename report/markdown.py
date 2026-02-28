"""Markdown 文件报告生成"""

import os
from datetime import datetime

from models import MarketReport
from config import OUTPUT_DIR


def save(report: MarketReport) -> str:
    """生成 Markdown 报告并保存到文件，返回文件路径"""
    session_label = "上午盘" if report.session == "morning" else "下午盘"
    session_tag = report.session or "manual"
    date_str = report.generated_at.strftime("%Y%m%d")
    filename = f"market_report_{date_str}_{session_tag}.md"

    # 确保输出目录存在（相对于项目根目录）
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(script_dir, OUTPUT_DIR)
    os.makedirs(out_dir, exist_ok=True)
    filepath = os.path.join(out_dir, filename)

    lines = []
    now = report.generated_at.strftime("%Y-%m-%d %H:%M")

    lines.append(f"# A股市场报告 — {now} ({session_label})\n")

    reasons = report.reasons or {}

    # --- 自选股 ---
    if report.watchlist is not None and not report.watchlist.empty:
        lines.append("## 自选股行情\n")
        lines.append(_watchlist_table(report.watchlist))

    # --- 关注板块 ---
    if report.watch_sectors:
        for sec in report.watch_sectors:
            lines.append(_watch_sector_section(sec))

    # --- 市场宽度 ---
    if report.stock:
        s = report.stock
        lines.append("## 市场宽度\n")
        lines.append(f"| 指标 | 数值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 上涨 | {s.up_count} |")
        lines.append(f"| 下跌 | {s.down_count} |")
        lines.append(f"| 平盘 | {s.flat_count} |")
        lines.append(f"| 涨停 | {s.limit_up_count} |")
        lines.append(f"| 跌停 | {s.limit_down_count} |")
        lines.append("")

    # --- 资金流向 ---
    if report.fund_flow:
        ff = report.fund_flow
        if not ff.sector_flow.empty:
            lines.append("## 板块资金流向 TOP\n")
            lines.append(_fund_sector_table(ff.sector_flow))
        if not ff.stock_inflow.empty:
            lines.append("## 个股主力净流入 TOP\n")
            lines.append(_fund_stock_table(ff.stock_inflow, reasons))
        if not ff.stock_outflow.empty:
            lines.append("## 个股主力净流出 TOP\n")
            lines.append(_fund_stock_table(ff.stock_outflow, reasons))

    # --- 板块 ---
    if report.sector:
        sec = report.sector
        lines.append("## 行业板块涨幅 TOP\n")
        lines.append(_sector_table(sec.top_gainers, reasons))
        lines.append("## 行业板块跌幅 TOP\n")
        lines.append(_sector_table(sec.top_losers, reasons))

        if not sec.concept_gainers.empty:
            lines.append("## 概念板块涨幅 TOP\n")
            lines.append(_sector_table(sec.concept_gainers, reasons))
        if not sec.concept_losers.empty:
            lines.append("## 概念板块跌幅 TOP\n")
            lines.append(_sector_table(sec.concept_losers, reasons))

    # --- 个股 ---
    if report.stock:
        s = report.stock
        lines.append("## 个股涨幅 TOP\n")
        lines.append(_stock_table(s.top_gainers, reasons=reasons))
        lines.append("## 个股跌幅 TOP\n")
        lines.append(_stock_table(s.top_losers, reasons=reasons))
        lines.append("## 成交额 TOP\n")
        lines.append(_stock_table(s.top_volume, show_volume=True))

    # --- 新闻 ---
    if report.news:
        if report.news.matched:
            lines.append("## 板块涨跌关联新闻\n")
            for sector, items in list(report.news.matched.items())[:10]:
                lines.append(f"### {sector}\n")
                for item in items[:3]:
                    time_str = ""
                    if item.publish_time:
                        time_str = f" ({item.publish_time.strftime('%H:%M')})"
                    lines.append(f"- {item.title[:80]}{time_str}")
                lines.append("")

        lines.append("## 最新财经要闻\n")
        seen = set()
        count = 0
        for item in report.news.items:
            title = item.title[:80]
            if title not in seen and count < 20:
                seen.add(title)
                count += 1
                time_str = ""
                if item.publish_time:
                    time_str = f" ({item.publish_time.strftime('%m-%d %H:%M')})"
                lines.append(f"{count}. {title}{time_str} — {item.source}")
        lines.append("")

    # --- 风险提示 ---
    lines.append("---\n")
    lines.append("*以上信息基于公开数据自动生成，不构成投资建议。股市有风险，投资需谨慎。*\n")

    content = "\n".join(lines)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath


# ---------- 辅助函数 ----------

def _fmt_amount(val) -> str:
    """金额格式化: 亿/万"""
    if val is None or val == 0:
        return "--"
    abs_val = abs(val)
    sign = "+" if val > 0 else "-"
    if abs_val >= 1e8:
        return f"{sign}{abs_val / 1e8:.2f}亿"
    if abs_val >= 1e4:
        return f"{sign}{abs_val / 1e4:.0f}万"
    return f"{sign}{abs_val:.0f}"


def _watchlist_table(df) -> str:
    """自选股行情表"""
    if df.empty:
        return "数据暂不可用\n"

    rows = [
        "| 代码 | 名称 | 最新价 | 涨跌幅 | 涨跌额 | 成交额 | 换手率 | 主力净流入 | 主力占比 |",
        "|------|------|--------|--------|--------|--------|--------|-----------|---------|",
    ]
    for _, row in df.iterrows():
        code = row.get("代码", "")
        name = row.get("名称", "")
        price = row.get("最新价", 0)
        chg_pct = row.get("涨跌幅", 0)
        chg_amt = row.get("涨跌额", 0)
        amount = row.get("成交额", 0)
        turnover = row.get("换手率", 0)
        main_flow = row.get("主力净流入", 0)
        main_pct = row.get("主力净流入占比", 0)

        price_str = f"{price:.2f}" if price else "--"
        chg_pct_str = f"{chg_pct:+.2f}%" if chg_pct is not None else "--"
        chg_amt_str = f"{chg_amt:+.2f}" if chg_amt is not None else "--"
        amount_str = f"{amount / 1e8:.2f}亿" if amount and amount > 0 else "--"
        turn_str = f"{turnover:.2f}%" if turnover else "--"
        flow_str = _fmt_amount(main_flow) if main_flow else "--"
        flow_pct_str = f"{main_pct:+.2f}%" if main_pct else "--"

        rows.append(
            f"| {code} | {name} | {price_str} | {chg_pct_str} | {chg_amt_str} | "
            f"{amount_str} | {turn_str} | {flow_str} | {flow_pct_str} |"
        )
    rows.append("")
    return "\n".join(rows)


def _watch_sector_section(sec_data: dict) -> str:
    """关注板块完整段落：板块概览 + 成分股明细"""
    name = sec_data["name"]
    ov = sec_data.get("overview", {})
    stocks = sec_data.get("stocks")

    lines = []
    lines.append(f"## 关注板块：{name}\n")

    # 概览
    chg = ov.get("涨跌幅", 0)
    main_flow = ov.get("主力净流入", 0)
    main_pct = ov.get("主力净流入占比", 0)
    total = ov.get("总数", 0)
    up = ov.get("上涨", 0)
    down = ov.get("下跌", 0)
    flat = ov.get("平盘", 0)
    limit_up = ov.get("涨停", 0)

    chg_str = f"{chg:+.2f}%" if chg else "--"
    lines.append(f"**板块涨跌幅: {chg_str}** | "
                 f"主力净流入: {_fmt_amount(main_flow)}({main_pct:+.2f}%) | "
                 f"成分股: {total}只 | "
                 f"涨:{up} 跌:{down} 平:{flat} 涨停:{limit_up}\n")

    # 成分股明细
    if stocks is not None and not stocks.empty:
        lines.append("| # | 代码 | 名称 | 最新价 | 涨跌幅 | 成交额 | 换手率 | 主力净流入 | 主力占比 |")
        lines.append("|---|------|------|--------|--------|--------|--------|-----------|---------|")
        for i, (_, row) in enumerate(stocks.iterrows()):
            code = row.get("代码", "")
            sname = row.get("名称", "")
            price = row.get("最新价", 0)
            s_chg = row.get("涨跌幅", 0)
            amount = row.get("成交额", 0)
            turnover = row.get("换手率", 0)
            s_flow = row.get("主力净流入", 0)
            s_pct = row.get("主力净流入占比", 0)

            price_str = f"{price:.2f}" if price else "--"
            chg_s = f"{s_chg:+.2f}%" if s_chg is not None else "--"
            amt_str = f"{amount / 1e8:.2f}亿" if amount and amount > 0 else "--"
            turn_str = f"{turnover:.2f}%" if turnover else "--"
            flow_str = _fmt_amount(s_flow) if s_flow else "--"
            pct_str = f"{s_pct:+.2f}%" if s_pct else "--"

            lines.append(
                f"| {i + 1} | {code} | {sname} | {price_str} | {chg_s} | "
                f"{amt_str} | {turn_str} | {flow_str} | {pct_str} |"
            )
        lines.append("")

    return "\n".join(lines)


def _sector_table(df, reasons=None) -> str:
    if df.empty:
        return "数据暂不可用\n"

    has_reasons = bool(reasons)

    if has_reasons:
        rows = ["| # | 板块名称 | 涨跌幅% | 相关原因 |",
                "|---|---------|---------|---------|"]
    else:
        rows = ["| # | 板块名称 | 涨跌幅% |", "|---|---------|---------|"]

    for i, (_, row) in enumerate(df.iterrows()):
        name = row.get("板块名称", "")
        chg = row.get("涨跌幅")
        chg_str = f"{chg:+.2f}%" if chg is not None else "--"
        if has_reasons:
            reason = reasons.get(f"sector:{name}", "")
            rows.append(f"| {i + 1} | {name} | {chg_str} | {reason} |")
        else:
            rows.append(f"| {i + 1} | {name} | {chg_str} |")
    rows.append("")
    return "\n".join(rows)


def _stock_table(df, show_volume=False, reasons=None) -> str:
    if df.empty:
        return "数据暂不可用\n"

    has_reasons = bool(reasons) and not show_volume

    header = "| # | 代码 | 名称 | 最新价 | 涨跌幅% |"
    sep = "|---|------|------|--------|---------|"
    if show_volume:
        header += " 成交额(亿) |"
        sep += "------------|"
    if has_reasons:
        header += " 涨跌原因 |"
        sep += "---------|"

    rows = [header, sep]
    for i, (_, row) in enumerate(df.iterrows()):
        code = row.get("代码", "")
        name = row.get("名称", "")
        price = row.get("最新价", 0)
        chg = row.get("涨跌幅")
        chg_str = f"{chg:+.2f}%" if chg is not None else "--"
        price_str = f"{price:.2f}" if price else "--"
        line = f"| {i + 1} | {code} | {name} | {price_str} | {chg_str} |"
        if show_volume:
            vol = row.get("成交额", 0)
            line += f" {vol / 1e8:.2f} |" if vol and vol > 0 else " -- |"
        if has_reasons:
            reason = reasons.get(f"stock:{code}", "")
            line += f" {reason} |"
        rows.append(line)
    rows.append("")
    return "\n".join(rows)


def _fund_sector_table(df) -> str:
    """板块资金流向表"""
    if df.empty:
        return "数据暂不可用\n"

    rows = [
        "| # | 板块 | 涨跌幅 | 主力净流入 | 主力占比 | 超大单 | 大单 |",
        "|---|------|--------|-----------|---------|--------|------|",
    ]
    for i, (_, row) in enumerate(df.iterrows()):
        name = row.get("名称", "")
        chg = row.get("涨跌幅", 0)
        main_flow = row.get("今日主力净流入-净额", 0)
        main_pct = row.get("今日主力净流入-净占比", 0)
        super_flow = row.get("今日超大单净流入-净额", 0)
        big_flow = row.get("今日大单净流入-净额", 0)

        chg_str = f"{chg:+.2f}%" if chg else "--"
        rows.append(
            f"| {i + 1} | {name} | {chg_str} | {_fmt_amount(main_flow)} | "
            f"{main_pct:+.2f}% | {_fmt_amount(super_flow)} | {_fmt_amount(big_flow)} |"
        )
    rows.append("")
    return "\n".join(rows)


def _fund_stock_table(df, reasons=None) -> str:
    """个股资金流向表"""
    if df.empty:
        return "数据暂不可用\n"

    has_price = "最新价" in df.columns
    has_reasons = reasons and any(
        f"stock:{row.get('代码', '')}" in reasons
        for _, row in df.iterrows()
    )

    if has_price:
        header = "| # | 代码 | 名称 | 最新价 | 涨跌幅 | 主力净流入 | 主力占比 |"
        sep = "|---|------|------|--------|--------|-----------|---------|"
    else:
        header = "| # | 代码 | 名称 | 主力净流入 | 主力占比 |"
        sep = "|---|------|------|-----------|---------|"
    if has_reasons:
        header += " 涨跌原因 |"
        sep += "---------|"
    rows = [header, sep]

    for i, (_, row) in enumerate(df.iterrows()):
        code = row.get("代码", "")
        name = row.get("名称", "")
        main_flow = row.get("今日主力净流入-净额", 0)
        main_pct = row.get("今日主力净流入-净占比", 0)
        reason_str = reasons.get(f"stock:{code}", "") if has_reasons else ""

        if has_price:
            price = row.get("最新价", 0)
            chg = row.get("涨跌幅", 0)
            price_str = f"{price:.2f}" if price else "--"
            chg_str = f"{chg:+.2f}%" if chg else "--"
            line = (f"| {i + 1} | {code} | {name} | {price_str} | {chg_str} | "
                    f"{_fmt_amount(main_flow)} | {main_pct:+.2f}% |")
        else:
            line = (f"| {i + 1} | {code} | {name} | "
                    f"{_fmt_amount(main_flow)} | {main_pct:+.2f}% |")
        if has_reasons:
            line += f" {reason_str} |"
        rows.append(line)
    rows.append("")
    return "\n".join(rows)
