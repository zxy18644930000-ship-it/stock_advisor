"""A股投资顾问 — Web 前端

启动方式：
    python3 web.py              # 默认 8088 端口
    python3 web.py --port 9090  # 自定义端口

浏览器打开 http://localhost:8088 即可查看报告。
"""

import os
import re
import argparse
from datetime import datetime

import markdown
from flask import Flask, render_template_string

# 项目根目录 & 报告目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

app = Flask(__name__)


# ─────────────────────── 工具函数 ───────────────────────

def _list_reports():
    """扫描 output/ 下的报告文件，按日期倒序返回"""
    if not os.path.isdir(OUTPUT_DIR):
        return []

    reports = []
    for fname in os.listdir(OUTPUT_DIR):
        if not fname.startswith("market_report_") or not fname.endswith(".md"):
            continue
        # market_report_20260227_morning.md
        m = re.match(r"market_report_(\d{8})_(morning|afternoon|manual)\.md", fname)
        if not m:
            continue
        date_str, session = m.group(1), m.group(2)
        session_cn = {"morning": "上午盘", "afternoon": "下午盘", "manual": "手动"}
        date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        reports.append({
            "filename": fname,
            "date": date_str,
            "date_fmt": date_fmt,
            "session": session,
            "session_cn": session_cn.get(session, session),
            "path": os.path.join(OUTPUT_DIR, fname),
        })
    # 按日期倒序，同日内 afternoon > morning > manual
    session_order = {"afternoon": 2, "morning": 1, "manual": 0}
    reports.sort(
        key=lambda r: (r["date"], session_order.get(r["session"], 0)),
        reverse=True,
    )
    return reports


def _read_report(filepath):
    """读取 md 文件并转为 HTML"""
    with open(filepath, "r", encoding="utf-8") as f:
        md_text = f.read()
    html = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
    return html


# ─────────────────────── HTML 模板 ───────────────────────

PAGE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>A股投资顾问</title>
<style>
  :root {
    --bg: #0f1117;
    --card: #1a1d28;
    --border: #2a2d3a;
    --text: #e0e0e0;
    --text2: #8b8fa3;
    --accent: #4e8cff;
    --red: #f5475b;
    --green: #26c968;
    --orange: #ff9f43;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC",
                 "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
  }

  /* ── 顶栏 ── */
  .topbar {
    background: var(--card);
    border-bottom: 1px solid var(--border);
    padding: 16px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
  }
  .topbar h1 {
    font-size: 20px;
    font-weight: 600;
    color: var(--accent);
  }
  .topbar .meta { font-size: 13px; color: var(--text2); }

  /* ── 布局 ── */
  .container {
    display: flex;
    min-height: calc(100vh - 60px);
  }

  /* ── 侧边栏 ── */
  .sidebar {
    width: 240px;
    min-width: 240px;
    background: var(--card);
    border-right: 1px solid var(--border);
    padding: 16px 0;
    overflow-y: auto;
  }
  .sidebar h3 {
    padding: 0 16px;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text2);
    margin-bottom: 8px;
  }
  .sidebar a {
    display: block;
    padding: 10px 16px;
    color: var(--text);
    text-decoration: none;
    font-size: 14px;
    border-left: 3px solid transparent;
    transition: all .15s;
  }
  .sidebar a:hover {
    background: rgba(78,140,255,.08);
    border-left-color: var(--accent);
  }
  .sidebar a.active {
    background: rgba(78,140,255,.12);
    border-left-color: var(--accent);
    color: var(--accent);
    font-weight: 500;
  }
  .sidebar .date-label {
    font-size: 13px;
  }
  .sidebar .session-label {
    font-size: 11px;
    color: var(--text2);
  }

  /* ── 主内容 ── */
  .main {
    flex: 1;
    padding: 24px 32px;
    max-width: 960px;
    overflow-y: auto;
  }

  /* ── 报告内容样式 ── */
  .report h1 {
    font-size: 22px;
    font-weight: 600;
    margin-bottom: 24px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border);
    color: var(--accent);
  }
  .report h2 {
    font-size: 16px;
    font-weight: 600;
    margin: 28px 0 12px;
    padding: 8px 12px;
    background: rgba(78,140,255,.08);
    border-left: 3px solid var(--accent);
    border-radius: 0 4px 4px 0;
  }
  .report h3 {
    font-size: 14px;
    margin: 16px 0 8px;
    color: var(--orange);
  }

  /* ── 表格 ── */
  .report table {
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0 20px;
    font-size: 13px;
  }
  .report thead th {
    background: var(--card);
    padding: 10px 12px;
    text-align: left;
    font-weight: 500;
    color: var(--text2);
    border-bottom: 2px solid var(--border);
    white-space: nowrap;
  }
  .report tbody td {
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
  }
  .report tbody tr:hover {
    background: rgba(78,140,255,.04);
  }

  /* ── 新闻列表 ── */
  .report ol, .report ul {
    padding-left: 20px;
    margin: 8px 0;
  }
  .report li {
    margin: 6px 0;
    font-size: 13px;
    line-height: 1.7;
  }
  .report p {
    margin: 8px 0;
    font-size: 13px;
  }
  .report em {
    color: var(--text2);
    font-size: 12px;
  }
  .report hr {
    border: none;
    border-top: 1px solid var(--border);
    margin: 24px 0;
  }

  /* ── 空状态 ── */
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 60vh;
    color: var(--text2);
  }
  .empty .icon { font-size: 48px; margin-bottom: 16px; }
  .empty p { font-size: 15px; }

  /* ── 涨跌颜色 ── */
  .report td:last-child,
  .report td:nth-last-child(2) {
    font-variant-numeric: tabular-nums;
  }

  /* ── 折叠按钮 ── */
  .collapse-btn {
    display: inline-block;
    margin: 6px 0 4px;
    padding: 4px 14px;
    font-size: 12px;
    color: var(--accent);
    background: rgba(78,140,255,.1);
    border: 1px solid rgba(78,140,255,.25);
    border-radius: 4px;
    cursor: pointer;
    transition: all .15s;
    user-select: none;
  }
  .collapse-btn:hover {
    background: rgba(78,140,255,.2);
  }
  .collapsible {
    overflow: hidden;
    transition: max-height .3s ease;
  }
  .collapsible.collapsed {
    max-height: 0 !important;
  }

  /* ── 响应式 ── */
  @media (max-width: 768px) {
    .sidebar { display: none; }
    .main { padding: 16px; }
    .topbar h1 { font-size: 16px; }
  }
</style>
</head>
<body>

<div class="topbar">
  <h1>A股投资顾问</h1>
  <div class="meta">{{ now }}</div>
</div>

<div class="container">
  <nav class="sidebar">
    <h3>历史报告</h3>
    {% for r in reports %}
    <a href="/report/{{ r.filename }}"
       class="{% if r.filename == current %}active{% endif %}">
      <div class="date-label">{{ r.date_fmt }}</div>
      <div class="session-label">{{ r.session_cn }}</div>
    </a>
    {% endfor %}
  </nav>

  <main class="main">
    {% if content %}
    <div class="report">{{ content|safe }}</div>
    {% else %}
    <div class="empty">
      <div class="icon">&#128200;</div>
      <p>暂无报告，等待下次收盘自动生成</p>
    </div>
    {% endif %}
  </main>
</div>

<script>
// 自动给涨跌幅加颜色
document.querySelectorAll('.report td').forEach(td => {
  const text = td.textContent.trim();
  if (/^\+\d/.test(text)) td.style.color = '#26c968';
  else if (/^-\d/.test(text)) td.style.color = '#f5475b';
});

// 关注板块成分股表格折叠
document.querySelectorAll('.report h2').forEach(h2 => {
  if (!h2.textContent.includes('关注板块')) return;

  // 找到 h2 后面的 table（跳过概览 p 标签）
  let table = null;
  let el = h2.nextElementSibling;
  while (el && el.tagName !== 'H2') {
    if (el.tagName === 'TABLE') { table = el; break; }
    el = el.nextElementSibling;
  }
  if (!table) return;

  // 包裹 table 到可折叠容器
  const wrapper = document.createElement('div');
  wrapper.className = 'collapsible collapsed';
  table.parentNode.insertBefore(wrapper, table);
  wrapper.appendChild(table);

  // 创建折叠按钮
  const btn = document.createElement('span');
  btn.className = 'collapse-btn';
  btn.textContent = '展开成分股明细 ▼';
  wrapper.parentNode.insertBefore(btn, wrapper);

  btn.addEventListener('click', () => {
    const isCollapsed = wrapper.classList.toggle('collapsed');
    if (isCollapsed) {
      btn.textContent = '展开成分股明细 ▼';
    } else {
      wrapper.style.maxHeight = table.scrollHeight + 'px';
      btn.textContent = '收起成分股明细 ▲';
    }
  });
});
</script>
</body>
</html>
"""


# ─────────────────────── 路由 ───────────────────────

@app.route("/")
def index():
    """首页 — 显示最新报告"""
    reports = _list_reports()
    content = ""
    current = ""
    if reports:
        current = reports[0]["filename"]
        content = _read_report(reports[0]["path"])
    return render_template_string(
        PAGE_TEMPLATE,
        reports=reports,
        content=content,
        current=current,
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/report/<filename>")
def report(filename):
    """查看指定报告"""
    # 安全检查
    if "/" in filename or ".." in filename:
        return "非法路径", 400
    filepath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.isfile(filepath):
        return "报告不存在", 404

    reports = _list_reports()
    content = _read_report(filepath)
    return render_template_string(
        PAGE_TEMPLATE,
        reports=reports,
        content=content,
        current=filename,
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


# ─────────────────────── 启动 ───────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A股投资顾问 Web 前端")
    parser.add_argument("--port", type=int, default=8088, help="监听端口 (默认 8088)")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址 (默认 0.0.0.0)")
    args = parser.parse_args()

    print(f"A股投资顾问 Web 前端已启动: http://localhost:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
