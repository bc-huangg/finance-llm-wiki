#!/usr/bin/env python3
"""Validation pipeline for the LLM Wiki -> HTML Slides workflow."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "raw"
WIKI_DIR = ROOT / "wiki"
DOCS_DIR = ROOT / "docs"
LOGS_DIR = ROOT / "pipeline" / "logs"

sys.path.insert(0, str(ROOT / "pipeline"))
import build_site  # noqa: E402

REQUIRED_FRONTMATTER = {"id", "title", "category", "summary", "sources", "updated", "tags"}
GUARANTEE_PHRASES = ["保證每年", "穩賺不賠", "保證獲利", "保證報酬"]
JARGON_BLOCKLIST = ["夏普值", "Beta 係數", "阿爾法"]
MAX_SLIDE_BODY_CHARS = 220


def load_raw_source_ids() -> set[str]:
    ids: set[str] = set()
    for p in RAW_DIR.glob("*.md"):
        text = p.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if m:
            meta = yaml.safe_load(m.group(1)) or {}
            if "source_id" in meta:
                ids.add(str(meta["source_id"]))
    return ids


def gate_1_lint_wiki() -> dict:
    raw_ids = load_raw_source_ids()
    files = sorted(WIKI_DIR.rglob("*.md"))
    parsed: list[tuple[Path, dict, str]] = []
    valid_wiki_ids: set[str] = set()
    errors: list[dict] = []

    for p in files:
        text = p.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
        if not m:
            errors.append({"gate": "Gate 1 (Wiki)", "code": "SCHEMA_MISSING", "file": str(p.relative_to(ROOT)), "detail": "Missing YAML frontmatter"})
            continue
        meta = yaml.safe_load(m.group(1)) or {}
        body = m.group(2)
        missing = sorted(REQUIRED_FRONTMATTER - set(meta.keys()))
        if missing:
            errors.append({"gate": "Gate 1 (Wiki)", "code": "SCHEMA_INCOMPLETE", "file": str(p.relative_to(ROOT)), "detail": f"Missing fields: {missing}"})
        pid = str(meta.get("id", p.stem))
        valid_wiki_ids.add(pid)
        parsed.append((p, meta, body))

    for p, meta, body in parsed:
        rel = p.relative_to(ROOT).as_posix()
        for sid in meta.get("sources", []):
            if sid not in raw_ids:
                errors.append({"gate": "Gate 1 (Wiki)", "code": "UNKNOWN_SOURCE", "file": rel, "detail": f"Unknown source_id: {sid}"})
        if not re.search(r"\[S[1-6]\]", body):
            errors.append({"gate": "Gate 1 (Wiki)", "code": "NO_INLINE_CITE", "file": rel, "detail": "No [S#] inline citation found"})
        for link in re.findall(r"\[\[([^\]]+)\]\]", body):
            if link.strip() not in valid_wiki_ids:
                errors.append({"gate": "Gate 1 (Wiki)", "code": "BROKEN_WIKILINK", "file": rel, "detail": f"Broken wikilink [[{link}]]"})

    return {
        "gate": "Gate 1: Ingest Quality Gate",
        "passed": len(errors) == 0,
        "wiki_pages_checked": len(files),
        "raw_sources_count": len(raw_ids),
        "valid_wiki_ids": sorted(valid_wiki_ids),
        "errors": errors,
    }


def gate_2_lint_outline(outline_path: Path, valid_wiki_ids: set[str], raw_ids: set[str], gate_label: str) -> dict:
    data = json.loads(outline_path.read_text(encoding="utf-8"))
    slides = data.get("slides", [])
    errors: list[dict] = []

    for s in slides:
        sid = s.get("id")
        bullets = s.get("bullets", [])
        takeaway = s.get("beginner_takeaway", "")
        combined = takeaway + " " + " ".join(bullets)

        # 1. Grounding check: prohibit ungrounded return guarantees
        for phrase in GUARANTEE_PHRASES:
            if phrase in combined:
                errors.append({
                    "gate": gate_label,
                    "code": "GROUNDING_ERROR",
                    "slide_id": sid,
                    "detail": f"包含未經來源證實的保證報酬宣稱「{phrase}」，與 Wiki 風險事實矛盾",
                })

        # 2. Citation coverage check
        wrefs = s.get("wiki_refs", [])
        srefs = s.get("source_ids", [])
        if not wrefs or not srefs:
            errors.append({
                "gate": gate_label,
                "code": "CITATION_MISSING",
                "slide_id": sid,
                "detail": "缺少 wiki_refs 或 source_ids 溯源標籤",
            })

        # 3. Valid wikilink refs check
        for wr in wrefs:
            if wr not in valid_wiki_ids:
                errors.append({
                    "gate": gate_label,
                    "code": "BROKEN_WIKILINK",
                    "slide_id": sid,
                    "detail": f"引用不存在的 Wiki 條目「{wr}」",
                })
        for sr in srefs:
            if sr not in raw_ids:
                errors.append({
                    "gate": gate_label,
                    "code": "UNKNOWN_SOURCE",
                    "slide_id": sid,
                    "detail": f"引用不存在的原始來源「{sr}」",
                })

        # 4. Beginner jargon check
        found_jargon = [j for j in JARGON_BLOCKLIST if j in combined]
        if found_jargon:
            errors.append({
                "gate": gate_label,
                "code": "JARGON_UNEXPLAINED",
                "slide_id": sid,
                "detail": f"出現未白話解釋的進階術語：{', '.join(found_jargon)}",
            })

        # 5. Density / readability check
        body_chars = sum(len(b) for b in bullets)
        if body_chars > MAX_SLIDE_BODY_CHARS:
            errors.append({
                "gate": gate_label,
                "code": "DENSITY_OVERFLOW",
                "slide_id": sid,
                "detail": f"單頁正文達 {body_chars} 字（上限 {MAX_SLIDE_BODY_CHARS} 字），新手閱讀負荷過高",
            })

    return {
        "gate": gate_label,
        "passed": len(errors) == 0,
        "slides_checked": len(slides),
        "errors": errors,
    }


def gate_3_lint_render(valid_wiki_ids: set[str]) -> dict:
    errors: list[dict] = []
    index_html_path = DOCS_DIR / "index.html"
    slides_html_path = DOCS_DIR / "slides.html"

    if not index_html_path.exists() or not slides_html_path.exists():
        errors.append({"gate": "Gate 3: Render Gate", "code": "MISSING_OUTPUT", "detail": "docs/index.html or docs/slides.html missing"})
        return {"gate": "Gate 3: Render Gate", "passed": False, "errors": errors}

    slides_html = slides_html_path.read_text(encoding="utf-8")
    index_html = index_html_path.read_text(encoding="utf-8")

    # Verify interactive widgets exist in slides.html
    for widget_id in ["calc-chart", "quiz-container"]:
        if widget_id not in slides_html:
            errors.append({"gate": "Gate 3: Render Gate", "code": "WIDGET_MISSING", "detail": f"Missing interactive element #{widget_id}"})

    # Verify all slide wiki_refs embedded in slides.html resolve to valid Wiki IDs
    m = re.search(r"const SLIDES = (\[.*?\]);\s*\n", slides_html)
    slides_count = 0
    if not m:
        errors.append({"gate": "Gate 3: Render Gate", "code": "EMBED_MISSING", "detail": "SLIDES JSON missing from docs/slides.html"})
    else:
        slides_data = json.loads(m.group(1))
        slides_count = len(slides_data)
        for s in slides_data:
            for wr in s.get("wiki_refs", []):
                if wr not in valid_wiki_ids:
                    errors.append({"gate": "Gate 3: Render Gate", "code": "BROKEN_SLIDE_WIKI_LINK", "slide_id": s.get("id"), "detail": f"Unresolved link index.html#{wr}"})

    return {
        "gate": "Gate 3: Static Site Render Gate",
        "passed": len(errors) == 0,
        "slides_rendered": slides_count,
        "index_html_bytes": len(index_html.encode("utf-8")),
        "slides_html_bytes": len(slides_html.encode("utf-8")),
        "errors": errors,
    }


def write_logs(mode: str, report: dict) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = LOGS_DIR / f"run_{mode}_report.json"
    md_path = LOGS_DIR / f"run_{mode}_summary.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Graph {mode.upper()} 執行檢查報告",
        "",
        f"- **執行時間**：{report['timestamp']}",
        f"- **最終狀態**：`{report['status']}`",
        f"- **總錯誤數**：{report['total_errors']}",
        "",
        "## 各節點／閘門檢查結果",
        "",
    ]
    for g in report["gates"]:
        status_str = "PASSED" if g["passed"] else f"FAILED ({len(g['errors'])} errors)"
        lines.append(f"### {g['gate']} — {status_str}")
        if g["errors"]:
            for err in g["errors"]:
                loc = f"Slide {err['slide_id']}" if "slide_id" in err else err.get("file", "")
                lines.append(f"- **[{err['code']}]** ({loc}): {err['detail']}")
        else:
            lines.append("- 無錯誤，全數通過。")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def run_v1() -> dict:
    raw_ids = load_raw_source_ids()
    g1 = gate_1_lint_wiki()
    valid_wiki_ids = set(g1["valid_wiki_ids"])
    # In v1 (naive), checks happen only at Post-Audit after drafting outline
    g_post = gate_2_lint_outline(ROOT / "pipeline" / "slides_outline_v1.json", valid_wiki_ids, raw_ids, "Post-Audit (Late Check)")
    total_errors = len(g1["errors"]) + len(g_post["errors"])
    report = {
        "mode": "v1",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "PASSED" if total_errors == 0 else "FAILED",
        "total_errors": total_errors,
        "gates": [g1, g_post],
    }
    write_logs("v1", report)
    return report


def run_v2() -> dict:
    raw_ids = load_raw_source_ids()
    g1 = gate_1_lint_wiki()
    valid_wiki_ids = set(g1["valid_wiki_ids"])
    g2 = gate_2_lint_outline(ROOT / "pipeline" / "slides_outline_v2.json", valid_wiki_ids, raw_ids, "Gate 2: Outline Grounding Gate")
    build_info = build_site.build_all()
    g3 = gate_3_lint_render(valid_wiki_ids)
    total_errors = len(g1["errors"]) + len(g2["errors"]) + len(g3["errors"])
    report = {
        "mode": "v2",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "PASSED" if total_errors == 0 else "FAILED",
        "total_errors": total_errors,
        "build_info": build_info,
        "gates": [g1, g2, g3],
    }
    write_logs("v2", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["v1", "v2"], default="v2")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()

    r1 = r2 = None
    if args.all or args.self_check or args.mode == "v1":
        r1 = run_v1()
        print(f"[v1] status={r1['status']} errors={r1['total_errors']}")
    if args.all or args.self_check or args.mode == "v2":
        r2 = run_v2()
        print(f"[v2] status={r2['status']} errors={r2['total_errors']} wiki_pages={r2['build_info']['wiki_pages_count']} slides={r2['build_info']['slides_count']}")

    if args.self_check:
        assert r1 is not None and r2 is not None
        v1_codes = {e["code"] for g in r1["gates"] for e in g["errors"]}
        expected_codes = {"GROUNDING_ERROR", "CITATION_MISSING", "BROKEN_WIKILINK", "JARGON_UNEXPLAINED", "DENSITY_OVERFLOW"}
        assert r1["status"] == "FAILED", "v1 should fail"
        assert expected_codes.issubset(v1_codes), f"Missing expected v1 error codes: {expected_codes - v1_codes}"
        assert r2["status"] == "PASSED" and r2["total_errors"] == 0, "v2 must pass with 0 errors"
        print("SELF-CHECK PASSED")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
