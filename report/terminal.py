"""Rich 终端报告渲染"""

from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from models import MarketReport

console = Console()


def render(report: MarketReport) -> None:
    """渲染完整市场报告到终端"""
    now = report.generated_at.strftime("%Y-%m-%d %H:%M")
    session_label = "上午盘" if report.session == "morning" else "下午盘"

    # ====== 报告头 ======
    console.print()
    console.print(Panel(
        f"[bold]A股每日投资顾问报告[/bold]\n"
        f"报告时间: {now}  ({session_label})",
        title="[bold cyan]A股投资顾问[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))

    # ====== 市场宽度 ======
    if report.stock:
        s = report.stock
        console.print()
        console.print("[bold]═══ 市场宽度 ═══[/bold]")
        console.print(
            f"  上涨 [red]{s.up_count}[/red]  下跌 [green]{s.down_count}[/green]  "
            f"平盘 {s.flat_count}  "
            f"涨停 [bold red]{s.limit_up_count}[/bold red]  "
            f"跌停 [bold green]{s.limit_down_count}[/bold green]"
        )

    # ====== 板块涨跌 ======
    if report.sector:
        _render_sector(report)

    # ====== 个股 TOP ======
    if report.stock:
        _render_stocks(report)

    # ====== 资金流向 ======
    if report.fund_flow:
        _render_fund_flow(report)

    # ====== 新闻 + 涨跌原因 ======
    if report.news:
        _render_news(report)

    # ====== 风险提示 ======
    console.print()
    console.print(Panel(
        "[bold red]风险提示[/bold red]\n"
        "以上信息基于公开数据自动生成，不构成投资建议。\n"
        "股市有风险，投资需谨慎。",
        border_style="dim",
    ))
    console.print()


# ---------- 板块 ----------

def _render_sector(report: MarketReport):
    sec = report.sector
    console.print()
    console.print("[bold red]═══ 行业板块 TOP 涨 ═══[/bold red]")
    _print_sector_table(sec.top_gainers)

    console.print()
    console.print("[bold green]═══ 行业板块 TOP 跌 ═══[/bold green]")
    _print_sector_table(sec.top_losers)

    if not sec.concept_gainers.empty:
        console.print()
        console.print("[bold red]═══ 概念板块 TOP 涨 ═══[/bold red]")
        _print_sector_table(sec.concept_gainers)

    if not sec.concept_losers.empty:
        console.print()
        console.print("[bold green]═══ 概念板块 TOP 跌 ═══[/bold green]")
        _print_sector_table(sec.concept_losers)


def _print_sector_table(df):
    if df.empty:
        console.print("  [dim]数据暂不可用[/dim]")
        return

    table = Table(show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("#", width=3, justify="center")
    table.add_column("板块名称", width=14)
    table.add_column("涨跌幅%", width=8, justify="right")
    if "总市值" in df.columns:
        table.add_column("总市值", width=12, justify="right")
    if "领涨股票" in df.columns:
        table.add_column("领涨股", width=10)

    for i, row in df.iterrows():
        chg = row.get("涨跌幅")
        chg_str = f"{chg:+.2f}%" if chg is not None else "--"
        color = "red" if chg and chg > 0 else "green" if chg and chg < 0 else ""
        chg_str = f"[{color}]{chg_str}[/{color}]" if color else chg_str

        cols = [str(i + 1), str(row.get("板块名称", "")), chg_str]
        if "总市值" in df.columns:
            mv = row.get("总市值")
            cols.append(f"{mv / 1e8:.0f}亿" if mv and mv > 0 else "--")
        if "领涨股票" in df.columns:
            cols.append(str(row.get("领涨股票", "")))
        table.add_row(*cols)

    console.print(table)


# ---------- 个股 ----------

def _render_stocks(report: MarketReport):
    s = report.stock
    console.print()
    console.print("[bold red]═══ 个股涨幅 TOP ═══[/bold red]")
    _print_stock_table(s.top_gainers)

    console.print()
    console.print("[bold green]═══ 个股跌幅 TOP ═══[/bold green]")
    _print_stock_table(s.top_losers)

    console.print()
    console.print("[bold yellow]═══ 成交额 TOP ═══[/bold yellow]")
    _print_stock_table(s.top_volume, show_volume=True)


def _print_stock_table(df, show_volume=False):
    if df.empty:
        console.print("  [dim]数据暂不可用[/dim]")
        return

    table = Table(show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("#", width=3, justify="center")
    table.add_column("代码", width=8)
    table.add_column("名称", width=10)
    table.add_column("最新价", width=8, justify="right")
    table.add_column("涨跌幅%", width=8, justify="right")
    if show_volume:
        table.add_column("成交额(亿)", width=10, justify="right")

    for i, row in df.iterrows():
        chg = row.get("涨跌幅")
        chg_str = f"{chg:+.2f}%" if chg is not None else "--"
        color = "red" if chg and chg > 0 else "green" if chg and chg < 0 else ""
        chg_str = f"[{color}]{chg_str}[/{color}]" if color else chg_str

        price = row.get("最新价", 0)
        price_str = f"{price:.2f}" if price else "--"

        cols = [str(i + 1), str(row.get("代码", "")), str(row.get("名称", "")),
                price_str, chg_str]
        if show_volume:
            vol = row.get("成交额", 0)
            cols.append(f"{vol / 1e8:.2f}" if vol and vol > 0 else "--")

        table.add_row(*cols)

    console.print(table)


# ---------- 资金流向 ----------

def _render_fund_flow(report: MarketReport):
    ff = report.fund_flow

    if not ff.sector_flow.empty:
        console.print()
        console.print("[bold yellow]═══ 板块资金流向 TOP ═══[/bold yellow]")
        _print_fund_table(ff.sector_flow, is_sector=True)

    if not ff.stock_inflow.empty:
        console.print()
        console.print("[bold red]═══ 个股主力净流入 TOP ═══[/bold red]")
        _print_fund_table(ff.stock_inflow, is_sector=False)

    if not ff.stock_outflow.empty:
        console.print()
        console.print("[bold green]═══ 个股主力净流出 TOP ═══[/bold green]")
        _print_fund_table(ff.stock_outflow, is_sector=False)


def _print_fund_table(df, is_sector=False):
    if df.empty:
        console.print("  [dim]数据暂不可用[/dim]")
        return

    table = Table(show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("#", width=3, justify="center")

    if is_sector:
        name_col = "名称" if "名称" in df.columns else df.columns[1]
        table.add_column("板块", width=14)
        flow_col = None
        for c in df.columns:
            if "净流入" in c and "净额" in c:
                flow_col = c
                break
        if flow_col:
            table.add_column("主力净流入", width=14, justify="right")
    else:
        name_col = "名称" if "名称" in df.columns else "股票简称"
        code_col = "代码" if "代码" in df.columns else "股票代码"
        table.add_column("代码", width=8)
        table.add_column("名称", width=10)
        flow_col = "今日主力净流入-净额"

        if flow_col not in df.columns:
            for c in df.columns:
                if "主力净流入" in c and "净额" in c:
                    flow_col = c
                    break
        table.add_column("主力净流入(万)", width=14, justify="right")

    for idx, (_, row) in enumerate(df.iterrows()):
        if is_sector:
            name_val = str(row.get(name_col, ""))
            cols = [str(idx + 1), name_val]
            if flow_col and flow_col in df.columns:
                val = row.get(flow_col, 0)
                val_str = f"{val / 1e4:.0f}万" if val else "--"
                color = "red" if val and val > 0 else "green"
                cols.append(f"[{color}]{val_str}[/{color}]")
        else:
            code_val = str(row.get(code_col, "")) if not is_sector else ""
            name_val = str(row.get(name_col, ""))
            cols = [str(idx + 1), code_val, name_val]
            if flow_col and flow_col in df.columns:
                val = row.get(flow_col, 0)
                val_str = f"{val / 1e4:.0f}" if val else "--"
                color = "red" if val and val > 0 else "green"
                cols.append(f"[{color}]{val_str}[/{color}]")

        table.add_row(*cols)

    console.print(table)


# ---------- 新闻 ----------

def _render_news(report: MarketReport):
    news = report.news
    if not news:
        return

    # 涨跌原因匹配
    if news.matched:
        console.print()
        console.print("[bold cyan]═══ 板块涨跌关联新闻 ═══[/bold cyan]")
        for sector, items in list(news.matched.items())[:10]:
            console.print(f"\n  [bold]{sector}[/bold]:")
            for item in items[:3]:
                time_str = ""
                if item.publish_time:
                    time_str = f" [dim]{item.publish_time.strftime('%H:%M')}[/dim]"
                console.print(f"    - {item.title[:60]}{time_str}")

    # 最新要闻
    console.print()
    console.print("[bold yellow]═══ 最新财经要闻 ═══[/bold yellow]")
    console.print()
    seen = set()
    count = 0
    for item in news.items:
        title = item.title[:80]
        if title not in seen and count < 15:
            seen.add(title)
            count += 1
            src_tag = f"[dim]{item.source}[/dim]"
            time_str = ""
            if item.publish_time:
                time_str = f" [dim]{item.publish_time.strftime('%m-%d %H:%M')}[/dim]"
            console.print(f"  {count:>2}. {title}{time_str} {src_tag}")
