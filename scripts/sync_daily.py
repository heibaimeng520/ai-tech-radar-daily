#!/usr/bin/env python3
"""Sync latest AI Tech Radar articles & daily cards from radar.zhangyejialaoda.com."""

from __future__ import annotations

import datetime as dt
import re
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

SITE = "https://radar.zhangyejialaoda.com"
UA = "ai-tech-radar-github-sync/1.0"
BJT = dt.timezone(dt.timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_feed(xml_text: str) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    items: list[dict[str, str]] = []
    for node in root.findall("./channel/item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        category = (node.findtext("category") or "AI 资讯").strip()
        desc = re.sub(r"\s+", " ", (node.findtext("description") or "")).strip()
        pub_raw = (node.findtext("pubDate") or "").strip()
        pub_bjt = ""
        if pub_raw:
            try:
                pub_bjt = parsedate_to_datetime(pub_raw).astimezone(BJT).strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                pub_bjt = ""
        if title and link:
            items.append(
                {
                    "title": title,
                    "link": link,
                    "category": category,
                    "desc": desc,
                    "pub_bjt": pub_bjt,
                }
            )
    return items


def clean_picks(picks_md: str) -> str:
    lines = picks_md.strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def write_daily_digest(today: dt.datetime, items: list[dict[str, str]], picks_md: str) -> Path:
    month_dir = ROOT / "digests" / today.strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)
    day_str = today.strftime("%Y-%m-%d")
    target = month_dir / f"{day_str}.md"

    lines = [
        f"# 科技猫粮 AI 日报归档 · {day_str}",
        "",
        f"> 原站在线阅读：<{SITE}/> · [专题聚合]({SITE}/topic/) · [全站归档]({SITE}/archive/) · [RSS]({SITE}/feed.xml)",
        "",
        f"同步时间（北京时间）：`{today.strftime('%Y-%m-%d %H:%M')}`",
        "",
        "## 📰 最新 25 条精选快讯",
        "",
    ]
    for it in items[:25]:
        meta = f"`{it['category']}`" + (f" · {it['pub_bjt']}" if it["pub_bjt"] else "")
        desc = f" — {it['desc']}" if it["desc"] else ""
        lines.append(f"- **[{it['title']}]({it['link']})** ({meta}){desc}")

    cleaned_picks = clean_picks(picks_md)
    if cleaned_picks:
        lines.extend(["", "---", "", "## 🎯 重点选题素材卡", "", cleaned_picks])

    lines.append("")
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def rebuild_index() -> None:
    digests_root = ROOT / "digests"
    digests_root.mkdir(parents=True, exist_ok=True)
    files = sorted(
        (p for p in digests_root.rglob("*.md") if p.name != "INDEX.md"),
        key=lambda p: p.stem,
        reverse=True,
    )
    lines = [
        "# 📚 科技猫粮每日归档索引",
        "",
        f"> 在线阅读最新内容：<{SITE}/> · [按主题浏览]({SITE}/topic/) · [站内全部归档]({SITE}/archive/)",
        "",
    ]
    for p in files:
        rel = p.relative_to(digests_root).as_posix()
        lines.append(f"- [{p.stem}](./{rel})")
    lines.append("")
    (digests_root / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")


def update_readme(today: dt.datetime, items: list[dict[str, str]], digest_path: Path) -> None:
    readme_path = ROOT / "README.md"
    src = readme_path.read_text(encoding="utf-8")
    start_marker = "<!-- LATEST-FEED:START -->"
    end_marker = "<!-- LATEST-FEED:END -->"
    assert start_marker in src and end_marker in src, "Missing LATEST-FEED markers in README.md"

    rel_digest = digest_path.relative_to(ROOT).as_posix()
    block = [
        f"_最后同步（北京时间）：{today.strftime('%Y-%m-%d %H:%M')} · [今日完整归档（{today.strftime('%Y-%m-%d')}）](./{rel_digest})_",
        "",
    ]
    for it in items[:15]:
        meta = f"`{it['category']}`" + (f" · {it['pub_bjt']}" if it["pub_bjt"] else "")
        block.append(f"- **[{it['title']}]({it['link']})** ({meta})")
    replacement = f"{start_marker}\n" + "\n".join(block) + f"\n{end_marker}"

    pattern = re.compile(rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}", re.S)
    updated = pattern.sub(replacement, src, count=1)
    readme_path.write_text(updated, encoding="utf-8")


def main() -> int:
    today = dt.datetime.now(BJT)
    feed_xml = fetch_text(f"{SITE}/feed.xml")
    items = parse_feed(feed_xml)
    if not items:
        raise RuntimeError("No items parsed from feed.xml")

    try:
        picks_md = fetch_text(f"{SITE}/picks.md")
    except Exception:
        picks_md = ""

    digest_path = write_daily_digest(today, items, picks_md)
    rebuild_index()
    update_readme(today, items, digest_path)
    print(f"Synced {len(items)} items; digest={digest_path.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
