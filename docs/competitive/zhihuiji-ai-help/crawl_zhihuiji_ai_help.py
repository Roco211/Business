#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Crawl official help materials for 智慧记AI进销存.

Outputs JSON + Markdown under this directory. Does not download large binaries;
video/image URLs are preserved as links/metadata only.
"""
import json
import os
import re
import time
import hashlib
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import html2text

BASE = "https://www.zhihuiji.cn"
ENTRY_URL = f"{BASE}/help/zhj-space"
SEED_URLS = [
    f"{BASE}/help/zhj-space/1636",  # 手册
    f"{BASE}/help/zhj-space/1826",  # 视频
]
OUT_DIR = "/root/business-clone/docs/competitive/zhihuiji-ai-help"
PAGES_DIR = os.path.join(OUT_DIR, "pages")
RAW_DIR = os.path.join(OUT_DIR, "raw")
UA = "Mozilla/5.0 (compatible; BusinessCompetitiveResearch/1.0; +local)"

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept": "text/html,application/json,*/*"})


def safe_slug(text, max_len=80):
    text = re.sub(r"[\\/:*?\"<>|\s]+", "-", text.strip())
    text = re.sub(r"-+", "-", text).strip("-._")
    return (text[:max_len] or "untitled")


def extract_initial_state(html):
    marker = "window.__INITIAL_STATE__="
    start = html.find(marker)
    if start < 0:
        raise ValueError("window.__INITIAL_STATE__ not found")
    start += len(marker)
    end = html.find(";(function", start)
    if end < 0:
        end = html.find("</script>", start)
    raw = html[start:end].strip().rstrip(";")
    return json.loads(raw)


def get(url, expect_json=False):
    r = session.get(url, timeout=25, verify=False)
    r.raise_for_status()
    if expect_json:
        return r.json(), r
    return r.text, r


def html_to_markdown(content):
    if not content:
        return ""
    # If content is just a media URL, keep it as a link.
    if re.match(r"^https?://", content.strip()):
        return content.strip() + "\n"
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.body_width = 0
    h.unicode_snob = True
    h.skip_internal_links = True
    return h.handle(content).strip() + "\n"


def visible_text_from_html(content):
    if not content or re.match(r"^https?://", content.strip()):
        return ""
    soup = BeautifulSoup(content, "html.parser")
    return soup.get_text("\n", strip=True)


def collect_media_urls(content):
    urls = []
    if not content:
        return urls
    if re.match(r"^https?://", content.strip()):
        return [content.strip()]
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup.find_all(["img", "video", "source", "a"]):
        for attr in ["src", "href"]:
            val = tag.get(attr)
            if val and re.match(r"^https?://", val):
                urls.append(val)
    return sorted(set(urls))


def main():
    os.makedirs(PAGES_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)
    failures = []
    seed_states = []
    discovered = {}
    categories = []

    # Fetch entry and seed pages.
    try:
        entry_html, _ = get(ENTRY_URL)
        with open(os.path.join(RAW_DIR, "entry_zhj-space.html"), "w", encoding="utf-8") as f:
            f.write(entry_html)
    except Exception as e:
        failures.append({"url": ENTRY_URL, "stage": "entry", "error": repr(e)})

    for url in SEED_URLS:
        try:
            html, _ = get(url)
            raw_name = "seed_" + safe_slug(url.replace(BASE, "")) + ".html"
            with open(os.path.join(RAW_DIR, raw_name), "w", encoding="utf-8") as f:
                f.write(html)
            state = extract_initial_state(html)
            seed_states.append({"url": url, "state": state})
            h = state.get("help", {})
            categories.extend(h.get("categoryTree", []))
            for item in h.get("contentByIds", []) or []:
                pid = int(item["id"])
                discovered[pid] = {**discovered.get(pid, {}), **item}
        except Exception as e:
            failures.append({"url": url, "stage": "seed", "error": repr(e)})

    pages = []
    converter_note = "requests + BeautifulSoup/html2text; parsed SSR window.__INITIAL_STATE__, then fetched /api/help/{id}."
    for i, (pid, meta) in enumerate(sorted(discovered.items()), 1):
        api_url = f"{BASE}/api/help/{pid}"
        page_url = f"{BASE}/help/{'video' if meta.get('is_video') else 'doc'}/{pid}"
        try:
            data, resp = get(api_url, expect_json=True)
            with open(os.path.join(RAW_DIR, f"api_{pid}.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            if not data.get("success", True) and data.get("code") != 200:
                raise RuntimeError(f"api returned non-success: {data}")
            detail = data.get("data") or {}
            merged = {**meta, **detail}
            content = merged.get("content") or ""
            md_body = html_to_markdown(content)
            media_urls = collect_media_urls(content)
            text = visible_text_from_html(content)
            is_video = int(merged.get("is_video") or 0) == 1
            title = merged.get("title") or meta.get("title") or f"help-{pid}"
            filename = f"{pid}-{'video' if is_video else 'doc'}-{safe_slug(title)}.md"
            md_path = os.path.join(PAGES_DIR, filename)
            frontmatter = {
                "id": pid,
                "title": title,
                "type": "video" if is_video else "doc",
                "url": page_url,
                "api_url": api_url,
                "category_id": merged.get("category_id"),
                "publish_time": merged.get("publish_time"),
                "create_time": merged.get("create_time"),
                "hits": merged.get("hits"),
                "thumbnail": merged.get("thumbnail"),
                "media_urls": media_urls,
            }
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("---\n")
                f.write(json.dumps(frontmatter, ensure_ascii=False, indent=2))
                f.write("\n---\n\n")
                f.write(f"# {title}\n\n")
                f.write(f"官方页面: {page_url}\n\n")
                if is_video:
                    f.write("视频/媒体链接（未下载大文件）:\n")
                    for u in media_urls or ([content.strip()] if content.strip().startswith("http") else []):
                        f.write(f"- {u}\n")
                    f.write("\n")
                f.write(md_body)
            pages.append({
                **frontmatter,
                "markdown_path": md_path,
                "raw_api_path": os.path.join(RAW_DIR, f"api_{pid}.json"),
                "content_text": text,
                "content_markdown": md_body,
                "source_meta": meta,
            })
            time.sleep(0.03)
        except Exception as e:
            failures.append({"url": api_url, "page_url": page_url, "stage": "detail", "id": pid, "title": meta.get("title"), "error": repr(e)})

    # Stable indexes/reports.
    pages_sorted = sorted(pages, key=lambda x: (x["type"], x["id"]))
    summary = {
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "entry_url": ENTRY_URL,
        "seed_urls": SEED_URLS,
        "method": converter_note,
        "output_dir": OUT_DIR,
        "pages_dir": PAGES_DIR,
        "raw_dir": RAW_DIR,
        "discovered_count": len(discovered),
        "saved_page_count": len(pages_sorted),
        "doc_count": sum(1 for p in pages_sorted if p["type"] == "doc"),
        "video_count": sum(1 for p in pages_sorted if p["type"] == "video"),
        "failure_count": len(failures),
        "failures": failures,
    }
    with open(os.path.join(OUT_DIR, "all_pages.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "categories": categories, "pages": pages_sorted}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "failures.json"), "w", encoding="utf-8") as f:
        json.dump(failures, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "INDEX.md"), "w", encoding="utf-8") as f:
        f.write("# 智慧记AI进销存官方帮助文档抓取索引\n\n")
        f.write(f"入口URL: {ENTRY_URL}\n\n")
        f.write(f"抓取方法: {converter_note}\n\n")
        f.write(f"页面数量: {len(pages_sorted)}（手册 {summary['doc_count']}，视频 {summary['video_count']}）\n\n")
        f.write(f"失败页面: {len(failures)}，详见 failures.json\n\n")
        f.write("## 页面列表\n\n")
        for p in pages_sorted:
            rel = os.path.relpath(p["markdown_path"], OUT_DIR)
            f.write(f"- [{p['id']}] [{p['type']}] {p['title']} - {p['url']} - `{rel}`\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # zhihuiji.cn certificate chain may fail in minimal containers; avoid noisy warnings.
    requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
    main()
