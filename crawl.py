#!/usr/bin/env python3
"""
Static mirror crawler for https://www.drszentgyorgyi.hu (Joomla site).
Downloads all internal HTML pages + assets, rewrites links to root-relative
static paths so the result can be hosted as-is on Cloudflare Pages.
Output goes into ./public
"""
import os
import re
import sys
import time
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag, unquote

import requests
from bs4 import BeautifulSoup

BASE = "https://www.drszentgyorgyi.hu"
HOST = "www.drszentgyorgyi.hu"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")

ASSET_EXT = {
    ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".webp", ".bmp", ".pdf", ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp4", ".webm", ".mp3", ".zip", ".doc", ".docx", ".xls", ".xlsx",
    ".ppt", ".pptx", ".json", ".xml", ".txt", ".rar",
}

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; SiteMirror/1.0)"})

visited_pages = set()
saved_assets = set()
queue = deque()

# Maps any in-domain absolute URL -> the public href we rewrite links to.
def is_same_host(url):
    try:
        return urlparse(url).netloc in ("", HOST)
    except Exception:
        return False

def ext_of(path):
    m = re.search(r"(\.[A-Za-z0-9]+)$", path)
    return m.group(1).lower() if m else ""

def is_asset_url(url):
    p = urlparse(url)
    return ext_of(p.path) in ASSET_EXT

def page_local_href(url):
    """Pretty root-relative URL used inside rewritten HTML for a page."""
    p = urlparse(url)
    path = p.path
    # strip leading /index.php
    if path.startswith("/index.php"):
        rem = path[len("/index.php"):]
    else:
        rem = path
    rem = rem.strip("/")
    if not rem:
        return "/"
    return "/" + rem + "/"

def page_local_file(url):
    href = page_local_href(url)
    if href == "/":
        return os.path.join(OUT, "index.html")
    rel = href.strip("/")
    return os.path.join(OUT, rel.replace("/", os.sep), "index.html")

def asset_local_href(url):
    p = urlparse(url)
    path = p.path.lstrip("/")
    return "/" + path

def asset_local_file(url):
    p = urlparse(url)
    rel = unquote(p.path.lstrip("/"))
    return os.path.join(OUT, rel.replace("/", os.sep))

def want_page(url):
    """Should this URL be crawled as an HTML page?"""
    if not is_same_host(url):
        return False
    p = urlparse(url)
    if is_asset_url(url):
        return False
    q = p.query
    # skip feeds, print/component views, raw format variants
    if "format=feed" in q or "format=raw" in q:
        return False
    if "tmpl=component" in q or "print=1" in q:
        return False
    # only crawl index.php-based pages or root
    if p.path in ("/", "/index.php") or p.path.startswith("/index.php/"):
        return True
    return False

def save_bytes(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)

def fetch(url):
    for attempt in range(3):
        try:
            r = session.get(url, timeout=30)
            return r
        except Exception as e:
            print(f"  ! error {url}: {e} (retry {attempt+1})")
            time.sleep(2)
    return None

def download_asset(url):
    url, _ = urldefrag(url)
    if url in saved_assets:
        return
    saved_assets.add(url)
    r = fetch(url)
    if r is None or r.status_code != 200:
        print(f"  asset FAIL {r.status_code if r else 'ERR'}: {url}")
        return
    path = asset_local_file(url)
    save_bytes(path, r.content)
    print(f"  asset {r.status_code}: {asset_local_href(url)}")
    # If CSS, parse url() references for more assets
    if ext_of(urlparse(url).path) == ".css":
        try:
            process_css(url, r.content, path)
        except Exception as e:
            print(f"  ! css parse {url}: {e}")

def process_css(css_url, content, local_path):
    text = content.decode("utf-8", "replace")
    urls = re.findall(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", text)
    imports = re.findall(r"@import\s+['\"]([^'\"]+)['\"]", text)
    for ref in urls + imports:
        ref = ref.strip()
        if ref.startswith("data:") or ref.startswith("#"):
            continue
        abs_url = urljoin(css_url, ref)
        if is_same_host(abs_url) and is_asset_url(abs_url):
            download_asset(abs_url)
            new = asset_local_href(abs_url)
            text = text.replace(ref, new)
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(text)

def rewrite_and_save_page(url, html):
    soup = BeautifulSoup(html, "html.parser")

    # remove <base> tag (breaks relative resolution once static)
    for b in soup.find_all("base"):
        b.decompose()

    def handle(attr_url):
        """Return rewritten value, and enqueue/download as needed."""
        if not attr_url:
            return None
        raw = attr_url.strip()
        if raw.startswith(("data:", "mailto:", "tel:", "javascript:", "#")):
            return None
        abs_url, frag = urldefrag(urljoin(url, raw))
        if not is_same_host(abs_url):
            return None  # leave external as-is
        if is_asset_url(abs_url):
            download_asset(abs_url)
            new = asset_local_href(abs_url)
            return new + (("#" + frag) if frag else "")
        if want_page(abs_url):
            if abs_url not in visited_pages and abs_url not in queue:
                queue.append(abs_url)
            new = page_local_href(abs_url)
            return new + (("#" + frag) if frag else "")
        return None

    for tag, attr in [("a", "href"), ("link", "href"), ("script", "src"),
                      ("img", "src"), ("source", "src"), ("iframe", "src"),
                      ("video", "src"), ("audio", "src"), ("embed", "src")]:
        for el in soup.find_all(tag):
            val = el.get(attr)
            if val:
                new = handle(val)
                if new is not None:
                    el[attr] = new
        # srcset
        if tag in ("img", "source"):
            for el in soup.find_all(tag):
                ss = el.get("srcset")
                if ss:
                    parts = []
                    for piece in ss.split(","):
                        piece = piece.strip()
                        if not piece:
                            continue
                        bits = piece.split()
                        u = bits[0]
                        new = handle(u)
                        if new is not None:
                            bits[0] = new
                        parts.append(" ".join(bits))
                    el["srcset"] = ", ".join(parts)

    out_path = page_local_file(url)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(str(soup))
    print(f"PAGE -> {page_local_href(url)}  ({out_path})")

def main():
    seeds = [BASE + "/index.php", BASE + "/"]
    for s in seeds:
        queue.append(s)
    count = 0
    while queue:
        url = queue.popleft()
        url, _ = urldefrag(url)
        # normalize home variants
        if url in visited_pages:
            continue
        visited_pages.add(url)
        if not want_page(url):
            continue
        r = fetch(url)
        if r is None or r.status_code != 200:
            print(f"PAGE FAIL {r.status_code if r else 'ERR'}: {url}")
            continue
        ctype = r.headers.get("Content-Type", "")
        if "text/html" not in ctype:
            # not html, treat as asset
            continue
        rewrite_and_save_page(url, r.text)
        count += 1
        time.sleep(0.3)
    print(f"\nDONE. {count} pages, {len(saved_assets)} assets.")

if __name__ == "__main__":
    main()
