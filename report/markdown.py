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

    # --- 板块 ---
    if report.sector:
        sec = report.sector
        lines.append("## 行业板块涨幅 TOP\n")
        lines.append(_sector_table(sec.top_gainers))
        lines.append("## 行业板块跌幅 TOP\n")
        lines.append(_sector_table(sec.top_losers))

        if not sec.concept_gainers.empty:
            lines.append("## 概念板块涨幅 TOP\n")
            lines.append(_sector_table(sec.concept_gainers))
        if not sec.concept_losers.empty:
            lines.append("## 概念板块跌幅 TOP\n")
            lines.append(_sector_table(sec.concept_losers))

    # --- 个股 ---
    if report.stock:
        s = report.stock
        lines.append("## 个股涨幅 TOP\n")
        lines.append(_stock_table(s.top_gainers))
        lines.append("## 个股跌幅 TOP\n")
        lines.append(_stock_table(s.top_losers))
        lines.append("## 成交额 TOP\n")
        lines.append(_stock_table(s.top_volume, show_volume=True))

    # --- 资金流向 ---
    if report.fund_flow:
        ff = report.fund_flow
        if not ff.sector_flow.empty:
            lines.append("## 板块资金流向 TOP\n")
            lines.append(_fund_table(ff.sector_flow, is_sector=True))
        if not ff.stock_inflow.empty:
            lines.append("## 个股主力净流入 TOP\n")
            lines.append(_fund_table(ff.stock_inflow, is_sector=False))
        if not ff.stock_outflow.empty:
            lines.append("## 个股主力净流出 TOP\n")
            lines.append(_fund_table(ff.stock_outflow, is_sector=False))

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

def _sector_table(df) -> str:
    if df.empty:
        return "数据暂不可用\n"

    rows = ["| # | 板块名称 | 涨跌幅% |", "|---|---------|---------|"]
    for i, (_, row) in enumerate(df.iterrows()):
        name = row.get("板块名称", "")
        chg = row.get("涨跌幅")
        chg_str = f"{chg:+.2f}%" if chg is not None else "--"
        rows.append(f"| {i + 1} | {name} | {chg_str} |")
    rows.append("")
    return "\n".join(rows)


def _stock_table(df, show_volume=False) -> str:
    if df.empty:
        return "数据暂不可用\n"

    header = "| # | 代码 | 名称 | 最新价 | 涨跌幅% |"
    sep = "|---|------|------|--------|---------|"
    if show_volume:
        header += " 成交额(亿) |"
        sep += "------------|"

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
        rows.append(line)
    rows.append("")
    return "\n".join(rows)


def _fund_table(df, is_sector=False) -> str:
    if df.empty:
        return "数据暂不可用\n"

    if is_sector:
        name_col = "名称" if "名称" in df.columns else df.columns[1]
        flow_col = None
        for c in df.columns:
            if "净流入" in c and "净额" in c:
                flow_col = c
                break

        rows = ["| # | 板块 | 主力净流入 |", "|---|------|-----------|"]
        for i, (_, row) in enumerate(df.iterrows()):
            name = row.get(name_col, "")
            val = row.get(flow_col, 0) if flow_col else 0
            val_str = f"{val / 1e4:.0f}万" if val else "--"
            rows.append(f"| {i + 1} | {name} | {val_str} |")
    else:
        name_col = "名称" if "名称" in df.columns else "股票简称"
        code_col = "代码" if "代码" in df.columns else "股票代码"
        flow_col = "今日主力净流入-净额"
        if flow_col not in df.columns:
            for c in df.columns:
                if "主力净流入" in c and "净额" in c:
                    flow_col = c
                    break

        rows = ["| # | 代码 | 名称 | 主力净流入(万) |", "|---|------|------|---------------|"]
        for i, (_, row) in enumerate(df.iterrows()):
            code = row.get(code_col, "")
            name = row.get(name_col, "")
            val = row.get(flow_col, 0) if flow_col in df.columns else 0
            val_str = f"{val / 1e4:.0f}" if val else "--"
            rows.append(f"| {i + 1} | {code} | {name} | {val_str} |")

    rows.append("")
    return "\n".join(rows)
