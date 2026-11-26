#!/usr/bin/env python3
"""Build static GitHub-Pages-ready LLM Wiki browser (docs/index.html)
and 12-slide interactive teaching presentation (docs/slides.html).
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
import markdown
import yaml

ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = ROOT / "wiki"
RAW_DIR = ROOT / "raw"
DOCS_DIR = ROOT / "docs"
OUTLINE_V2 = ROOT / "pipeline" / "slides_outline_v2.json"

CATEGORY_LABELS = {
    "foundations": "一、財務基石",
    "instruments": "二、指數與 ETF 原理",
    "strategies": "三、新手實作策略",
    "risk": "四、風險與行為防線",
    "sources": "五、權威來源摘要",
}

CATEGORY_ORDER = ["foundations", "instruments", "strategies", "risk", "sources"]


def parse_frontmatter(text: str) -> tuple[dict, str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not match:
        return {}, text
    meta = yaml.safe_load(match.group(1)) or {}
    return meta, match.group(2)


def render_markdown_with_links(body: str, valid_ids: set[str]) -> tuple[str, list[str]]:
    referenced_ids: list[str] = []

    def replace_wikilink(m: re.Match) -> str:
        target = m.group(1).strip()
        if target not in referenced_ids:
            referenced_ids.append(target)
        cls = "wikilink" if target in valid_ids else "wikilink broken"
        return f'<a href="#{html.escape(target)}" class="{cls}" data-target="{html.escape(target)}">[[{html.escape(target)}]]</a>'

    def replace_cite(m: re.Match) -> str:
        sid = m.group(1)
        target = f"source-{sid}"
        return f'<a href="#{target}" class="cite-badge" title="查看來源 {sid}">[{sid}]</a>'

    processed = re.sub(r"\[\[([^\]]+)\]\]", replace_wikilink, body)
    processed = re.sub(r"\[(S[1-6])\]", replace_cite, processed)
    rendered = markdown.markdown(
        processed,
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    return rendered, referenced_ids


def load_wiki_pages() -> tuple[list[dict], dict[str, dict]]:
    raw_files = sorted(WIKI_DIR.rglob("*.md"))
    parsed: list[tuple[dict, str, str]] = []
    valid_ids: set[str] = set()

    for path in raw_files:
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        pid = meta.get("id", path.stem)
        valid_ids.add(pid)
        rel = path.relative_to(ROOT).as_posix()
        parsed.append((meta, body, rel))

    pages: list[dict] = []
    by_id: dict[str, dict] = {}
    for meta, body, rel in parsed:
        pid = meta.get("id", Path(rel).stem)
        html_body, outlinks = render_markdown_with_links(body, valid_ids)
        page = {
            "id": pid,
            "title": meta.get("title", pid),
            "category": meta.get("category", "foundations"),
            "category_label": CATEGORY_LABELS.get(meta.get("category", ""), "其他"),
            "summary": meta.get("summary", ""),
            "sources": meta.get("sources", []),
            "updated": str(meta.get("updated", "")),
            "tags": meta.get("tags", []),
            "path": rel,
            "outlinks": outlinks,
            "backlinks": [],
            "html": html_body,
        }
        pages.append(page)
        by_id[pid] = page

    # Compute automatic backlinks
    for page in pages:
        for target_id in page["outlinks"]:
            if target_id in by_id and target_id != page["id"]:
                if not any(b["id"] == page["id"] for b in by_id[target_id]["backlinks"]):
                    by_id[target_id]["backlinks"].append({
                        "id": page["id"],
                        "title": page["title"],
                    })

    # Add special index virtual page
    index_md = (ROOT / "index.md").read_text(encoding="utf-8")
    index_html, _ = render_markdown_with_links(index_md, valid_ids)

    special_pages = [
        {
            "id": "index",
            "title": "知識庫總目錄（Wiki Index）",
            "category": "meta",
            "category_label": "知識庫導覽",
            "summary": "瀏覽個人理財與指數投資入門 LLM Wiki 的四大模組與 6 篇權威來源。",
            "sources": ["S1", "S2", "S3", "S4", "S5", "S6"],
            "updated": "2026-11-26",
            "tags": ["總目錄", "導覽"],
            "path": "index.md",
            "outlinks": [],
            "backlinks": [],
            "html": index_html,
        },
    ]
    return special_pages + pages, by_id


def build_wiki_html(all_pages: list[dict]) -> str:
    pages_json = json.dumps(all_pages, ensure_ascii=False)
    cat_order_json = json.dumps(CATEGORY_ORDER, ensure_ascii=False)
    cat_labels_json = json.dumps(CATEGORY_LABELS, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>個人理財與指數投資入門 — LLM Wiki 知識庫</title>
  <style>
    :root {{
      --bg: #FAF9F6;
      --surface: #FFFFFF;
      --navy: #14213D;
      --emerald: #0F766E;
      --emerald-soft: #E6F4F1;
      --amber: #D97706;
      --amber-soft: #FEF3C7;
      --ink: #1F2937;
      --muted: #6B7280;
      --border: #E5E7EB;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Noto Sans TC", "Microsoft JhengHei", "PingFang TC", system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.72;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 20;
      background: var(--navy);
      color: #fff;
      padding: 14px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      box-shadow: 0 2px 10px rgba(20, 33, 61, 0.14);
    }}
    .brand {{ display: flex; flex-direction: column; }}
    .brand-title {{ font-size: 1.08rem; font-weight: 700; letter-spacing: 0.02em; }}
    .brand-sub {{ font-size: 0.78rem; color: #CBD5E1; }}
    .cta-btn {{
      background: var(--emerald);
      color: #fff;
      text-decoration: none;
      padding: 9px 16px;
      border-radius: 8px;
      font-weight: 600;
      font-size: 0.9rem;
      white-space: nowrap;
      transition: background 0.15s ease;
    }}
    .cta-btn:hover {{ background: #0D625B; }}
    .layout {{
      max-width: 1360px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: 300px 1fr;
      gap: 28px;
      padding: 24px;
      align-items: start;
    }}
    aside {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
      position: sticky;
      top: 82px;
      max-height: calc(100vh - 106px);
      overflow-y: auto;
    }}
    .search-box {{
      width: 100%;
      padding: 9px 12px;
      border: 1px solid var(--border);
      border-radius: 8px;
      font-size: 0.9rem;
      font-family: inherit;
      margin-bottom: 14px;
      background: var(--bg);
    }}
    .nav-group {{ margin-bottom: 14px; }}
    .nav-group-title {{
      font-size: 0.76rem;
      font-weight: 700;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin: 8px 0 6px 6px;
    }}
    .nav-item {{
      display: block;
      padding: 7px 10px;
      border-radius: 8px;
      text-decoration: none;
      color: var(--ink);
      font-size: 0.88rem;
      line-height: 1.4;
      margin-bottom: 2px;
    }}
    .nav-item:hover {{ background: #F3F4F6; }}
    .nav-item.active {{
      background: var(--emerald-soft);
      color: var(--emerald);
      font-weight: 700;
    }}
    main {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 32px 38px;
      min-height: 75vh;
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03);
    }}
    .meta-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin-bottom: 12px;
    }}
    .cat-pill {{
      background: var(--navy);
      color: #fff;
      font-size: 0.76rem;
      font-weight: 600;
      padding: 3px 10px;
      border-radius: 999px;
    }}
    .tag-pill {{
      background: #F3F4F6;
      color: #374151;
      font-size: 0.76rem;
      padding: 3px 9px;
      border-radius: 999px;
    }}
    .source-pill {{
      background: var(--amber-soft);
      color: #92400E;
      text-decoration: none;
      font-size: 0.76rem;
      font-weight: 600;
      padding: 3px 9px;
      border-radius: 999px;
    }}
    .summary-callout {{
      background: var(--emerald-soft);
      border-left: 4px solid var(--emerald);
      padding: 12px 16px;
      border-radius: 0 10px 10px 0;
      margin: 14px 0 24px 0;
      font-size: 0.96rem;
      color: #0F4C46;
    }}
    article h1 {{ font-size: 1.85rem; color: var(--navy); margin: 0 0 12px 0; line-height: 1.3; }}
    article h2 {{ font-size: 1.25rem; color: var(--navy); margin-top: 26px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }}
    article h3 {{ font-size: 1.05rem; color: var(--emerald); margin-top: 18px; }}
    article table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 0.92rem; }}
    article th, article td {{ border: 1px solid var(--border); padding: 9px 12px; text-align: left; }}
    article th {{ background: #F8FAFC; color: var(--navy); }}
    .wikilink {{
      background: var(--emerald-soft);
      color: var(--emerald);
      text-decoration: none;
      padding: 1px 6px;
      border-radius: 6px;
      font-weight: 600;
      font-size: 0.92em;
    }}
    .wikilink:hover {{ text-decoration: underline; }}
    .wikilink.broken {{ background: #FEE2E2; color: #B91C1C; }}
    .cite-badge {{
      color: var(--amber);
      font-weight: 700;
      text-decoration: none;
      font-size: 0.85em;
      margin-left: 2px;
    }}
    .backlinks-box {{
      margin-top: 34px;
      padding-top: 18px;
      border-top: 1px dashed var(--border);
    }}
    .backlinks-title {{ font-size: 0.92rem; font-weight: 700; color: var(--muted); margin-bottom: 10px; }}
    .backlinks-list {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .backlink-chip {{
      background: #F8FAFC;
      border: 1px solid var(--border);
      color: var(--navy);
      text-decoration: none;
      padding: 5px 11px;
      border-radius: 8px;
      font-size: 0.85rem;
    }}
    .backlink-chip:hover {{ border-color: var(--emerald); color: var(--emerald); }}
    @media (max-width: 900px) {{
      .layout {{ grid-template-columns: 1fr; }}
      aside {{ position: static; max-height: none; }}
      main {{ padding: 22px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="brand-title">個人理財與指數投資入門 — LLM Wiki</div>
      <div class="brand-sub">台灣新手視角 · 6 篇公開來源 · 17 篇知識條目</div>
    </div>
    <a class="cta-btn" href="./slides.html">開啟教學 HTML 簡報（12 頁） →</a>
  </header>

  <div class="layout">
    <aside>
      <input id="searchInput" class="search-box" type="search" placeholder="搜尋 Wiki 條目或關鍵字..." />
      <div id="sidebarNav"></div>
    </aside>
    <main>
      <div id="articleContainer"></div>
    </main>
  </div>

  <script>
    const WIKI_PAGES = {pages_json};
    const CATEGORY_ORDER = {cat_order_json};
    const CATEGORY_LABELS = {cat_labels_json};
    const PAGE_MAP = Object.fromEntries(WIKI_PAGES.map(p => [p.id, p]));

    function getCurrentId() {{
      const h = (window.location.hash || "#index").replace(/^#/, "");
      return PAGE_MAP[h] ? h : "index";
    }}

    function renderSidebar(filterText = "") {{
      const q = filterText.trim().toLowerCase();
      const nav = document.getElementById("sidebarNav");
      const currentId = getCurrentId();
      const groups = [];

      const metaPages = WIKI_PAGES.filter(p => p.category === "meta");
      groups.push({{ label: "知識庫導覽", items: metaPages }});
      for (const cat of CATEGORY_ORDER) {{
        const items = WIKI_PAGES.filter(p => p.category === cat);
        groups.push({{ label: CATEGORY_LABELS[cat], items }});
      }}

      let html = "";
      for (const g of groups) {{
        const matched = g.items.filter(p => {{
          if (!q) return true;
          return (p.title + " " + p.summary + " " + (p.tags || []).join(" ")).toLowerCase().includes(q);
        }});
        if (!matched.length) continue;
        html += `<div class="nav-group"><div class="nav-group-title">${{g.label}}</div>`;
        for (const p of matched) {{
          const active = p.id === currentId ? "active" : "";
          html += `<a href="#${{p.id}}" class="nav-item ${{active}}">${{p.title}}</a>`;
        }}
        html += `</div>`;
      }}
      nav.innerHTML = html || '<div style="color:#6B7280;font-size:0.88rem;">找不到符合的條目</div>';
    }}

    function renderArticle() {{
      const id = getCurrentId();
      const page = PAGE_MAP[id];
      const container = document.getElementById("articleContainer");

      const sourcesHtml = (page.sources || [])
        .map(s => `<a href="#source-${{s}}" class="source-pill">來源 ${{s}}</a>`)
        .join("");
      const tagsHtml = (page.tags || [])
        .map(t => `<span class="tag-pill">#${{t}}</span>`)
        .join("");
      const backlinksHtml = (page.backlinks && page.backlinks.length)
        ? `<div class="backlinks-box">
             <div class="backlinks-title">反向連結（引用本條目的頁面）：</div>
             <div class="backlinks-list">
               ${{page.backlinks.map(b => `<a class="backlink-chip" href="#${{b.id}}">← ${{b.title}}</a>`).join("")}}
             </div>
           </div>`
        : "";

      container.innerHTML = `
        <div class="meta-bar">
          <span class="cat-pill">${{page.category_label}}</span>
          ${{sourcesHtml}}
          ${{tagsHtml}}
        </div>
        ${{page.summary ? `<div class="summary-callout"><strong>一句話重點：</strong>${{page.summary}}</div>` : ""}}
        <article>${{page.html}}</article>
        ${{backlinksHtml}}
      `;
      renderSidebar(document.getElementById("searchInput").value);
      window.scrollTo({{ top: 0, behavior: "smooth" }});
    }}

    document.getElementById("searchInput").addEventListener("input", (e) => {{
      renderSidebar(e.target.value);
    }});
    window.addEventListener("hashchange", renderArticle);
    renderArticle();
  </script>
</body>
</html>
"""


def build_slides_html(outline: dict, page_titles: dict[str, str]) -> str:
    slides_json = json.dumps(outline["slides"], ensure_ascii=False)
    titles_json = json.dumps(page_titles, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(outline["title"])} — 教學型 HTML 簡報</title>
  <style>
    :root {{
      --bg: #FAF9F6;
      --card: #FFFFFF;
      --navy: #14213D;
      --emerald: #0F766E;
      --emerald-soft: #E6F4F1;
      --amber: #D97706;
      --amber-soft: #FEF3C7;
      --ink: #1F2937;
      --muted: #6B7280;
      --border: #E5E7EB;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Noto Sans TC", "Microsoft JhengHei", "PingFang TC", system-ui, sans-serif;
      background: #F1F5F9;
      color: var(--ink);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    .topbar {{
      background: var(--navy);
      color: #fff;
      padding: 10px 22px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}
    .topbar a {{
      color: #E2E8F0;
      text-decoration: none;
      font-size: 0.88rem;
      font-weight: 600;
    }}
    .topbar a:hover {{ color: #fff; }}
    .progress-wrap {{ height: 4px; background: #CBD5E1; width: 100%; }}
    .progress-fill {{ height: 100%; background: var(--emerald); transition: width 0.25s ease; }}
    .stage {{
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }}
    .slide-card {{
      width: 100%;
      max-width: 1180px;
      min-height: 620px;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 18px;
      box-shadow: 0 14px 36px rgba(20, 33, 61, 0.08);
      padding: 36px 44px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .slide-header {{ margin-bottom: 18px; }}
    .slide-kicker {{
      font-size: 0.82rem;
      font-weight: 700;
      color: var(--emerald);
      letter-spacing: 0.04em;
      margin-bottom: 6px;
    }}
    .slide-title {{
      font-size: 1.78rem;
      font-weight: 800;
      color: var(--navy);
      margin: 0 0 6px 0;
      line-height: 1.28;
    }}
    .slide-subtitle {{ font-size: 0.98rem; color: var(--muted); margin: 0; }}
    .takeaway-box {{
      background: var(--emerald-soft);
      border-left: 4px solid var(--emerald);
      padding: 10px 14px;
      border-radius: 0 10px 10px 0;
      font-size: 0.94rem;
      color: #0F4C46;
      margin: 12px 0 18px 0;
    }}
    .slide-body {{
      display: grid;
      grid-template-columns: 1fr 1.08fr;
      gap: 26px;
      align-items: center;
      flex: 1;
    }}
    .slide-body.single {{ grid-template-columns: 1fr; }}
    .bullets {{
      margin: 0;
      padding-left: 20px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      font-size: 0.98rem;
      line-height: 1.62;
    }}
    .visual-panel {{
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 18px;
    }}
    .slide-footer {{
      margin-top: 22px;
      padding-top: 14px;
      border-top: 1px solid var(--border);
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}
    .wiki-refs {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
    .wiki-ref-label {{ font-size: 0.8rem; color: var(--muted); font-weight: 700; }}
    .wiki-pill {{
      background: #EFF6FF;
      color: var(--navy);
      border: 1px solid #BFDBFE;
      text-decoration: none;
      font-size: 0.78rem;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: 999px;
    }}
    .wiki-pill:hover {{ background: var(--emerald-soft); border-color: var(--emerald); color: var(--emerald); }}
    .nav-controls {{ display: flex; align-items: center; gap: 10px; }}
    button.nav-btn {{
      background: var(--navy);
      color: #fff;
      border: none;
      padding: 8px 14px;
      border-radius: 8px;
      font-family: inherit;
      font-weight: 600;
      cursor: pointer;
    }}
    button.nav-btn:disabled {{ opacity: 0.35; cursor: not-allowed; }}
    button.ghost-btn {{
      background: #E2E8F0;
      color: var(--navy);
      border: none;
      padding: 7px 12px;
      border-radius: 8px;
      font-family: inherit;
      font-weight: 600;
      cursor: pointer;
    }}
    .drawer {{
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.55);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 50;
      padding: 20px;
    }}
    .drawer.open {{ display: flex; }}
    .drawer-box {{
      background: #fff;
      border-radius: 16px;
      max-width: 780px;
      width: 100%;
      max-height: 82vh;
      overflow-y: auto;
      padding: 24px;
    }}
    .drawer-item {{
      display: flex;
      gap: 12px;
      padding: 10px 12px;
      border-radius: 10px;
      cursor: pointer;
      border: 1px solid transparent;
    }}
    .drawer-item:hover {{ background: #F8FAFC; border-color: var(--border); }}
    .drawer-item.active {{ background: var(--emerald-soft); border-color: var(--emerald); }}
    table.cmp {{ width: 100%; border-collapse: collapse; font-size: 0.86rem; }}
    table.cmp th, table.cmp td {{ border: 1px solid var(--border); padding: 8px 10px; text-align: left; }}
    table.cmp th {{ background: var(--navy); color: #fff; }}
    .calc-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }}
    .calc-ctrl label {{ display: flex; justify-content: space-between; font-size: 0.84rem; font-weight: 700; margin-bottom: 4px; }}
    .calc-ctrl input[type="range"] {{ width: 100%; accent-color: var(--emerald); }}
    .calc-stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 10px; }}
    .stat-box {{ background: #fff; border: 1px solid var(--border); border-radius: 10px; padding: 8px 10px; text-align: center; }}
    .stat-val {{ font-size: 1.02rem; font-weight: 800; color: var(--navy); }}
    .stat-lbl {{ font-size: 0.74rem; color: var(--muted); }}
    .quiz-q {{ background: #fff; border: 1px solid var(--border); border-radius: 10px; padding: 12px; margin-bottom: 10px; }}
    .quiz-opts {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
    .quiz-opt {{
      border: 1px solid var(--border);
      background: var(--bg);
      padding: 6px 11px;
      border-radius: 8px;
      cursor: pointer;
      font-family: inherit;
      font-size: 0.83rem;
    }}
    .quiz-opt.correct {{ background: #D1FAE5; border-color: #059669; color: #065F46; font-weight: 700; }}
    .quiz-opt.wrong {{ background: #FEE2E2; border-color: #DC2626; color: #991B1B; }}
    .quiz-fb {{ margin-top: 6px; font-size: 0.82rem; color: var(--navy); }}
    @media (max-width: 920px) {{
      .slide-body {{ grid-template-columns: 1fr; }}
      .slide-card {{ padding: 24px; }}
      .calc-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="topbar">
    <a href="./index.html">← 回到 LLM Wiki 知識庫</a>
    <div style="font-size:0.9rem;font-weight:700;">個人理財與指數投資入門（台灣新手版）</div>
    <div style="display:flex;gap:8px;align-items:center;">
      <button class="ghost-btn" id="openDrawerBtn">目錄總覽</button>
      <span id="pageCounter" style="font-size:0.86rem;font-weight:700;">1 / 12</span>
    </div>
  </div>
  <div class="progress-wrap"><div class="progress-fill" id="progressFill" style="width:8.3%"></div></div>

  <div class="stage">
    <div class="slide-card" id="slideCard"></div>
  </div>

  <div class="drawer" id="drawer">
    <div class="drawer-box">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
        <h3 style="margin:0;color:var(--navy);">簡報目錄（12 頁）</h3>
        <button class="ghost-btn" id="closeDrawerBtn">關閉</button>
      </div>
      <div id="drawerList"></div>
    </div>
  </div>

  <script>
    const SLIDES = {slides_json};
    const WIKI_TITLES = {titles_json};
    let currentIndex = 0;

    function parseHashSlide() {{
      const n = parseInt((window.location.hash || "#1").replace("#", ""), 10);
      if (!isNaN(n) && n >= 1 && n <= SLIDES.length) return n - 1;
      return 0;
    }}

    function fmtTWD(num) {{
      return "NT$ " + Math.round(num).toLocaleString("zh-TW");
    }}

    function renderVisual(slide) {{
      switch (slide.visual_type) {{
        case "cover":
          return `
            <div style="display:flex;flex-direction:column;gap:12px;">
              <div style="background:var(--navy);color:#fff;padding:16px;border-radius:12px;">
                <div style="font-size:0.8rem;color:#93C5FD;font-weight:700;">學習路線圖</div>
                <div style="font-size:1.1rem;font-weight:700;margin-top:4px;">四大模組 × 12 頁實戰入門</div>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                <div style="background:#fff;border:1px solid var(--border);padding:12px;border-radius:10px;"><strong>1. 財務基石</strong><br><span style="font-size:0.82rem;color:var(--muted);">預備金 · 通膨 · 複利</span></div>
                <div style="background:#fff;border:1px solid var(--border);padding:12px;border-radius:10px;"><strong>2. 指數原理</strong><br><span style="font-size:0.82rem;color:var(--muted);">SPIVA · ETF · 0050/VT</span></div>
                <div style="background:#fff;border:1px solid var(--border);padding:12px;border-radius:10px;"><strong>3. 實作策略</strong><br><span style="font-size:0.82rem;color:var(--muted);">股債配置 · 定期定額</span></div>
                <div style="background:#fff;border:1px solid var(--border);padding:12px;border-radius:10px;"><strong>4. 風險防線</strong><br><span style="font-size:0.82rem;color:var(--muted);">波動心態 · 金管會防詐</span></div>
              </div>
            </div>`;
        case "inflation_bars":
          return `
            <div style="font-weight:700;color:var(--navy);margin-bottom:8px;">NT$100,000 在年均通膨 2.5% 下的實質購買力</div>
            <svg viewBox="0 0 420 205" style="width:100%;height:auto;">
              <rect x="35" y="25" width="75" height="140" rx="6" fill="#0F766E"/>
              <text x="72" y="18" text-anchor="middle" font-size="12" font-weight="700" fill="#14213D">100,000</text>
              <text x="72" y="185" text-anchor="middle" font-size="12" fill="#374151">第 0 年</text>
              <rect x="170" y="56" width="75" height="109" rx="6" fill="#D97706"/>
              <text x="207" y="49" text-anchor="middle" font-size="12" font-weight="700" fill="#14213D">78,120</text>
              <text x="207" y="185" text-anchor="middle" font-size="12" fill="#374151">第 10 年</text>
              <rect x="305" y="80" width="75" height="85" rx="6" fill="#DC2626"/>
              <text x="342" y="73" text-anchor="middle" font-size="12" font-weight="700" fill="#991B1B">61,027</text>
              <text x="342" y="185" text-anchor="middle" font-size="12" fill="#374151">第 20 年</text>
            </svg>`;
        case "safety_layers":
          return `
            <div style="display:flex;flex-direction:column;gap:10px;">
              <div style="background:#ECFDF5;border:1px solid #059669;padding:12px;border-radius:10px;">
                <strong style="color:#065F46;">第 1 層：緊急預備金（先完成）</strong><br>
                <span style="font-size:0.84rem;">3–6 個月必要生活費（高利活存 / 短天期定存，隨時可領）</span>
              </div>
              <div style="background:#EFF6FF;border:1px solid #2563EB;padding:12px;border-radius:10px;">
                <strong style="color:#1E40AF;">第 2 層：長期指數核心（5 年以上閒錢）</strong><br>
                <span style="font-size:0.84rem;">低成本市值型 ETF（0050 / VT / VWRA），定期定額長期持有</span>
              </div>
              <div style="background:#FEF3C7;border:1px solid #D97706;padding:12px;border-radius:10px;">
                <strong style="color:#92400E;">防線鐵律</strong><br>
                <span style="font-size:0.84rem;">絕不拿預備金買股票，避免跌市被迫認賠殺出</span>
              </div>
            </div>`;
        case "calculator":
          return `
            <div>
              <div class="calc-grid">
                <div class="calc-ctrl">
                  <label>每月投入 <span id="lblMonthly">NT$ 10,000</span></label>
                  <input type="range" id="inMonthly" min="3000" max="30000" step="1000" value="10000">
                </div>
                <div class="calc-ctrl">
                  <label>投資年數 <span id="lblYears">25 年</span></label>
                  <input type="range" id="inYears" min="10" max="40" step="1" value="25">
                </div>
                <div class="calc-ctrl" style="grid-column:span 2;">
                  <label>市場年化報酬率（扣費前） <span id="lblRate">7.0%</span></label>
                  <input type="range" id="inRate" min="4" max="9" step="0.5" value="7">
                </div>
              </div>
              <svg id="calc-chart" viewBox="0 0 460 175" style="width:100%;height:auto;background:#fff;border:1px solid var(--border);border-radius:10px;"></svg>
              <div class="calc-stats" id="calcStats"></div>
            </div>`;
        case "spiva_bars":
          return `
            <div style="font-weight:700;color:var(--navy);margin-bottom:8px;">SPIVA 實證：主動型美國大型股基金落後 S&P 500 比例</div>
            <svg viewBox="0 0 430 190" style="width:100%;height:auto;">
              <text x="10" y="42" font-size="13" font-weight="700" fill="#14213D">10 年期</text>
              <rect x="90" y="24" width="248" height="26" rx="6" fill="#D97706"/>
              <text x="346" y="42" font-size="13" font-weight="700" fill="#92400E">83%–86%</text>
              <text x="10" y="96" font-size="13" font-weight="700" fill="#14213D">15 年期</text>
              <rect x="90" y="78" width="271" height="26" rx="6" fill="#DC2626"/>
              <text x="369" y="96" font-size="13" font-weight="700" fill="#991B1B">90.49%</text>
              <text x="10" y="150" font-size="13" font-weight="700" fill="#14213D">20 年期</text>
              <rect x="90" y="132" width="278" height="26" rx="6" fill="#991B1B"/>
              <text x="376" y="150" font-size="13" font-weight="700" fill="#991B1B">&gt; 92%</text>
            </svg>`;
        case "etf_flow":
          return `
            <div style="font-weight:700;color:var(--navy);margin-bottom:8px;">ETF 雙市場與折溢價套利機制</div>
            <svg viewBox="0 0 440 205" style="width:100%;height:auto;">
              <rect x="15" y="20" width="175" height="68" rx="10" fill="#EFF6FF" stroke="#14213D"/>
              <text x="102" y="46" text-anchor="middle" font-size="13" font-weight="700" fill="#14213D">初級市場（AP 法人）</text>
              <text x="102" y="68" text-anchor="middle" font-size="11" fill="#374151">一籃子股票 ⇄ ETF 申購/贖回</text>
              <rect x="250" y="20" width="175" height="68" rx="10" fill="#E6F4F1" stroke="#0F766E"/>
              <text x="337" y="46" text-anchor="middle" font-size="13" font-weight="700" fill="#0F766E">次級市場（一般散戶）</text>
              <text x="337" y="68" text-anchor="middle" font-size="11" fill="#374151">券商 App 盤中依「市價」買賣</text>
              <path d="M192 54 L248 54" stroke="#14213D" stroke-width="2.5" marker-end="url(#arr)"/>
              <rect x="35" y="118" width="370" height="68" rx="10" fill="#FEF3C7" stroke="#D97706"/>
              <text x="220" y="143" text-anchor="middle" font-size="13" font-weight="700" fill="#92400E">折溢價自動收斂</text>
              <text x="220" y="165" text-anchor="middle" font-size="11.5" fill="#78350F">溢價（市價 &gt; 淨值）→ 法人申購賣出壓低市價；折價則反向買進</text>
            </svg>`;
        case "fee_breakdown":
          return `
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
              <div style="background:#fff;border:1px solid var(--border);padding:14px;border-radius:10px;">
                <div style="font-weight:700;color:var(--navy);margin-bottom:6px;">交易外扣成本（買賣時付）</div>
                <ul style="margin:0;padding-left:18px;font-size:0.86rem;line-height:1.6;">
                  <li>券商手續費上限：<strong>0.1425%</strong>（電子下單常打折）</li>
                  <li>賣出證交稅（股票型 ETF）：<strong>0.1%</strong></li>
                </ul>
              </div>
              <div style="background:#fff;border:1px solid var(--border);padding:14px;border-radius:10px;">
                <div style="font-weight:700;color:var(--emerald);margin-bottom:6px;">內扣費用率（每日自淨值扣）</div>
                <ul style="margin:0;padding-left:18px;font-size:0.86rem;line-height:1.6;">
                  <li>0050 經理費：<strong>0.0688%–0.1%</strong></li>
                  <li>0050 保管費：<strong>0.025%–0.03%</strong></li>
                  <li>VOO：<strong>0.03%</strong>｜VT：<strong>0.06%</strong></li>
                </ul>
              </div>
            </div>`;
        case "comparison_table":
          return `
            <table class="cmp">
              <thead>
                <tr><th>標的</th><th>涵蓋市場</th><th>內扣費用率</th><th>台灣投資人重點</th></tr>
              </thead>
              <tbody>
                <tr><td><strong>0050</strong></td><td>台股市值前 50 大</td><td>經理 0.0688–0.1%<br>保管 0.025–0.03%</td><td>台幣交易、證交稅 0.1%、門檻最低</td></tr>
                <tr><td><strong>VOO</strong></td><td>美國 S&amp;P 500</td><td><strong>0.03%</strong></td><td>單一美國市場；配息預扣 30% 稅</td></tr>
                <tr><td><strong>VT</strong></td><td>全球逾 10,000 股</td><td><strong>0.06%</strong></td><td>一檔買下全世界；美股預扣 30% 稅</td></tr>
                <tr><td><strong>VWRA</strong></td><td>全球大中型企業</td><td><strong>0.14%</strong></td><td>愛爾蘭累積型；預扣稅降至 15%</td></tr>
              </tbody>
            </table>`;
        case "allocation_donut":
          return `
            <div style="display:flex;flex-direction:column;gap:14px;">
              <div>
                <div style="font-size:0.86rem;font-weight:700;margin-bottom:4px;">積極成長型（80% 股票 / 20% 債券）</div>
                <div style="display:flex;height:26px;border-radius:8px;overflow:hidden;">
                  <div style="width:80%;background:var(--navy);color:#fff;font-size:0.78rem;display:flex;align-items:center;justify-content:center;">80% 全球股票</div>
                  <div style="width:20%;background:var(--emerald);color:#fff;font-size:0.78rem;display:flex;align-items:center;justify-content:center;">20% 債</div>
                </div>
              </div>
              <div>
                <div style="font-size:0.86rem;font-weight:700;margin-bottom:4px;">穩健平衡型（60% 股票 / 40% 債券）</div>
                <div style="display:flex;height:26px;border-radius:8px;overflow:hidden;">
                  <div style="width:60%;background:var(--navy);color:#fff;font-size:0.78rem;display:flex;align-items:center;justify-content:center;">60% 全球股票</div>
                  <div style="width:40%;background:var(--emerald);color:#fff;font-size:0.78rem;display:flex;align-items:center;justify-content:center;">40% 債券緩衝</div>
                </div>
              </div>
              <div style="font-size:0.83rem;color:var(--muted);">Bogleheads 三基金核心：本國股市 ＋ 國際股市 ＋ 綜合債券</div>
            </div>`;
        case "rebalance_steps":
          return `
            <div style="display:flex;flex-direction:column;gap:10px;">
              <div style="background:#fff;border:1px solid var(--border);padding:11px;border-radius:10px;"><strong>Step 1：定期定額自動扣款</strong> — 發薪日隔天自動買進，不猜高低點</div>
              <div style="background:#fff;border:1px solid var(--border);padding:11px;border-radius:10px;"><strong>Step 2：新資金補齊低配部位</strong> — 哪邊比例低就多買哪邊，零賣出省稅費</div>
              <div style="background:#fff;border:1px solid var(--border);padding:11px;border-radius:10px;"><strong>Step 3：年度或 5/25 門檻檢視</strong> — 偏離達 5% 絕對值或 25% 相對值才調整</div>
            </div>`;
        case "pitfalls_grid":
          return `
            <div style="display:flex;flex-direction:column;gap:10px;">
              <div style="background:#FEF2F2;border:1px solid #FCA5A5;padding:10px 12px;border-radius:10px;font-size:0.86rem;">
                <strong>五大誤區避雷：</strong>無預備金 All-in · 飆股群組 · 頻繁短線 · 只看配息忽略費用 · 高溢價追買
              </div>
              <div style="background:#ECFDF5;border:1px solid #059669;padding:12px;border-radius:10px;font-size:0.86rem;">
                <strong style="color:#065F46;">台灣合法保護網：</strong><br>
                認明<strong>金管會（FSC）</strong>監理之合法金融機構開戶；遇上市櫃不法損害可洽<strong>投保中心（SFIPC）</strong>協助團體訴訟或調處。
              </div>
            </div>`;
        case "quiz_and_roadmap":
          return `
            <div id="quiz-container">
              <div class="quiz-q" data-ans="1" data-exp="緊急預備金必須放在高流動性保本帳戶，應準備 3–6 個月必要生活費（見 emergency-fund）。">
                <strong>Q1：剛出社會想投資，應該把全副身家都拿去買 0050 嗎？</strong>
                <div class="quiz-opts">
                  <button class="quiz-opt" data-idx="0">是，越早全押越好</button>
                  <button class="quiz-opt" data-idx="1">否，先存 3–6 個月必要生活費預備金</button>
                </div>
                <div class="quiz-fb"></div>
              </div>
              <div class="quiz-q" data-ans="1" data-exp="SPIVA 顯示 15 年期高達 90.49% 主動大型股基金落後 S&P 500（見 active-vs-passive）。">
                <strong>Q2：SPIVA 15 年期統計中，多數主動基金的表現如何？</strong>
                <div class="quiz-opts">
                  <button class="quiz-opt" data-idx="0">超過 8 成贏過大盤</button>
                  <button class="quiz-opt" data-idx="1">約 90.49% 落後 S&amp;P 500</button>
                </div>
                <div class="quiz-fb"></div>
              </div>
              <div class="quiz-q" data-ans="0" data-exp="VWRA 為愛爾蘭註冊累積型 ETF，美股股息預扣稅降至 15%（見 tw-0050-vs-global-etf）。">
                <strong>Q3：愛爾蘭註冊的 VWRA 相較美股 VT，預扣股息稅率為多少？</strong>
                <div class="quiz-opts">
                  <button class="quiz-opt" data-idx="0">15%（且股息自動再投入）</button>
                  <button class="quiz-opt" data-idx="1">30%</button>
                </div>
                <div class="quiz-fb"></div>
              </div>
            </div>`;
        default:
          return "";
      }}
    }}

    function attachCalcListeners() {{
      const mEl = document.getElementById("inMonthly");
      const yEl = document.getElementById("inYears");
      const rEl = document.getElementById("inRate");
      if (!mEl) return;

      function updateCalc() {{
        const monthly = Number(mEl.value);
        const years = Number(yEl.value);
        const grossRate = Number(rEl.value) / 100;
        document.getElementById("lblMonthly").textContent = fmtTWD(monthly);
        document.getElementById("lblYears").textContent = years + " 年";
        document.getElementById("lblRate").textContent = (grossRate * 100).toFixed(1) + "%";

        const ptsLow = [], ptsHigh = [];
        let balLow = 0, balHigh = 0;
        const rLow = (grossRate - 0.001) / 12;
        const rHigh = (grossRate - 0.015) / 12;
        for (let y = 0; y <= years; y++) {{
          ptsLow.push(balLow);
          ptsHigh.push(balHigh);
          for (let m = 0; m < 12; m++) {{
            balLow = (balLow + monthly) * (1 + rLow);
            balHigh = (balHigh + monthly) * (1 + rHigh);
          }}
        }}
        const maxVal = Math.max(ptsLow[years], 1);
        const W = 440, H = 150, padL = 16, padB = 18;
        const toPath = (arr) => arr.map((v, i) => {{
          const x = padL + (i / years) * (W - padL - 10);
          const y = H - (v / maxVal) * (H - 18);
          return `${{i === 0 ? "M" : "L"}}${{x.toFixed(1)}},${{y.toFixed(1)}}`;
        }}).join(" ");

        document.getElementById("calc-chart").innerHTML = `
          <path d="${{toPath(ptsLow)}}" fill="none" stroke="#0F766E" stroke-width="3.2"/>
          <path d="${{toPath(ptsHigh)}}" fill="none" stroke="#D97706" stroke-width="2.8" stroke-dasharray="6 4"/>
          <text x="20" y="20" font-size="11" font-weight="700" fill="#0F766E">低費用 ETF (0.1%)</text>
          <text x="155" y="20" font-size="11" font-weight="700" fill="#D97706">高費用基金 (1.5%)</text>
        `;
        const diff = ptsLow[years] - ptsHigh[years];
        document.getElementById("calcStats").innerHTML = `
          <div class="stat-box"><div class="stat-val" style="color:var(--emerald);">${{fmtTWD(ptsLow[years])}}</div><div class="stat-lbl">低費用 0.1% 終值</div></div>
          <div class="stat-box"><div class="stat-val" style="color:var(--amber);">${{fmtTWD(ptsHigh[years])}}</div><div class="stat-lbl">高費用 1.5% 終值</div></div>
          <div class="stat-box"><div class="stat-val" style="color:#DC2626;">+${{fmtTWD(diff)}}</div><div class="stat-lbl">省下費用多出的資產</div></div>
        `;
      }}
      mEl.addEventListener("input", updateCalc);
      yEl.addEventListener("input", updateCalc);
      rEl.addEventListener("input", updateCalc);
      updateCalc();
    }}

    function attachQuizListeners() {{
      document.querySelectorAll("#quiz-container .quiz-q").forEach(qEl => {{
        const ans = Number(qEl.dataset.ans);
        const exp = qEl.dataset.exp;
        const fb = qEl.querySelector(".quiz-fb");
        qEl.querySelectorAll(".quiz-opt").forEach(btn => {{
          btn.addEventListener("click", () => {{
            qEl.querySelectorAll(".quiz-opt").forEach(b => b.classList.remove("correct", "wrong"));
            const idx = Number(btn.dataset.idx);
            if (idx === ans) {{
              btn.classList.add("correct");
              fb.textContent = "✓ 答對了！" + exp;
            }} else {{
              btn.classList.add("wrong");
              fb.textContent = "✗ 再想一下：" + exp;
            }}
          }});
        }});
      }});
    }}

    function renderSlide(idx) {{
      currentIndex = Math.max(0, Math.min(SLIDES.length - 1, idx));
      const slide = SLIDES[currentIndex];
      window.history.replaceState(null, "", "#" + (currentIndex + 1));

      document.getElementById("pageCounter").textContent = `${{currentIndex + 1}} / ${{SLIDES.length}}`;
      document.getElementById("progressFill").style.width = `${{((currentIndex + 1) / SLIDES.length) * 100}}%`;

      const bulletsHtml = slide.bullets.map(b => `<li>${{b}}</li>`).join("");
      const refsHtml = (slide.wiki_refs || []).map(id => {{
        const t = WIKI_TITLES[id] || id;
        const shortTitle = t.split("：")[0];
        return `<a class="wiki-pill" href="./index.html#${{id}}" title="${{t}}">參考：${{shortTitle}}</a>`;
      }}).join("");

      document.getElementById("slideCard").innerHTML = `
        <div>
          <div class="slide-header">
            <div class="slide-kicker">第 ${{slide.id}} / ${{SLIDES.length}} 頁</div>
            <h1 class="slide-title">${{slide.title}}</h1>
            <p class="slide-subtitle">${{slide.subtitle || ""}}</p>
          </div>
          <div class="takeaway-box"><strong>核心一句話：</strong>${{slide.beginner_takeaway}}</div>
        </div>
        <div class="slide-body">
          <ul class="bullets">${{bulletsHtml}}</ul>
          <div class="visual-panel">${{renderVisual(slide)}}</div>
        </div>
        <div class="slide-footer">
          <div class="wiki-refs">
            <span class="wiki-ref-label">知識溯源：</span>
            ${{refsHtml}}
          </div>
          <div class="nav-controls">
            <button class="nav-btn" id="prevBtn" ${{currentIndex === 0 ? "disabled" : ""}}>← 上一頁</button>
            <button class="nav-btn" id="nextBtn" ${{currentIndex === SLIDES.length - 1 ? "disabled" : ""}}>下一頁 →</button>
          </div>
        </div>
      `;

      document.getElementById("prevBtn").addEventListener("click", () => renderSlide(currentIndex - 1));
      document.getElementById("nextBtn").addEventListener("click", () => renderSlide(currentIndex + 1));
      attachCalcListeners();
      attachQuizListeners();
      renderDrawer();
    }}

    function renderDrawer() {{
      document.getElementById("drawerList").innerHTML = SLIDES.map((s, i) => `
        <div class="drawer-item ${{i === currentIndex ? "active" : ""}}" data-idx="${{i}}">
          <strong style="color:var(--emerald);min-width:28px;">#${{s.id}}</strong>
          <div>
            <div style="font-weight:700;font-size:0.92rem;color:var(--navy);">${{s.title}}</div>
            <div style="font-size:0.78rem;color:var(--muted);">Wiki：${{(s.wiki_refs || []).join(", ")}}</div>
          </div>
        </div>
      `).join("");
      document.querySelectorAll(".drawer-item").forEach(el => {{
        el.addEventListener("click", () => {{
          document.getElementById("drawer").classList.remove("open");
          renderSlide(Number(el.dataset.idx));
        }});
      }});
    }}

    document.getElementById("openDrawerBtn").addEventListener("click", () => document.getElementById("drawer").classList.add("open"));
    document.getElementById("closeDrawerBtn").addEventListener("click", () => document.getElementById("drawer").classList.remove("open"));
    document.addEventListener("keydown", (e) => {{
      if (e.key === "ArrowRight") renderSlide(currentIndex + 1);
      if (e.key === "ArrowLeft") renderSlide(currentIndex - 1);
    }});
    window.addEventListener("hashchange", () => renderSlide(parseHashSlide()));

    renderSlide(parseHashSlide());
  </script>
</body>
</html>
"""


def build_all() -> dict:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    all_pages, by_id = load_wiki_pages()
    outline = json.loads(OUTLINE_V2.read_text(encoding="utf-8"))

    wiki_html = build_wiki_html(all_pages)
    (DOCS_DIR / "index.html").write_text(wiki_html, encoding="utf-8")

    page_titles = {pid: p["title"] for pid, p in by_id.items()}
    slides_html = build_slides_html(outline, page_titles)
    (DOCS_DIR / "slides.html").write_text(slides_html, encoding="utf-8")

    return {
        "wiki_pages_count": len(by_id),
        "slides_count": len(outline["slides"]),
        "index_bytes": (DOCS_DIR / "index.html").stat().st_size,
        "slides_bytes": (DOCS_DIR / "slides.html").stat().st_size,
    }


if __name__ == "__main__":
    info = build_all()
    print(json.dumps(info, ensure_ascii=False, indent=2))
