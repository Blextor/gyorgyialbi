#!/usr/bin/env python3
"""
Fix Joomla blog pagination for static hosting.

The main crawler collapsed each paginated category (page 1 = no query,
page 2 = ?start=N) onto a single file, so only the last page survived.
This script re-fetches every page of each paginated category, saves them as
separate static files (/slug/ = page 1, /slug/2/, /slug/3/ ...) and rewrites
the pager links so the pages cross-link statically (no query strings).
"""
import os
import re
from urllib.parse import urljoin, urlparse, urldefrag, parse_qs

import crawl  # reuse helpers; import does not run main()
from bs4 import BeautifulSoup

PUB = crawl.OUT
BASE = crawl.BASE


def find_paginated_categories():
    """Return list of slug paths (relative URL dirs) whose index.html paginates."""
    slugs = []
    for root, _, files in os.walk(PUB):
        for f in files:
            if f != "index.html":
                continue
            p = os.path.join(root, f)
            s = open(p, encoding="utf-8", errors="replace").read()
            m = re.search(r'class="counter"[^>]*>\s*\d+\.\s*oldal\s*/\s*(\d+)', s)
            if 'class="pagination"' in s and m and int(m.group(1)) > 1:
                rel = os.path.relpath(root, PUB).replace(os.sep, "/")
                slugs.append(rel)
    return slugs


def discover_starts(slug):
    """Fetch page 1 and return ordered list of start values for all pages."""
    url = f"{BASE}/index.php/{slug}"
    r = crawl.fetch(url)
    if r is None or r.status_code != 200:
        return None, None
    html = r.text
    starts = set()
    for m in re.findall(r'[?&]start=(\d+)', html):
        starts.add(int(m))
    starts.discard(0)
    ordered = sorted(starts)
    return html, ordered


def build_page_map(slug, ordered_starts):
    """start value -> (href, local_file). Page 1 (start 0/absent) included."""
    m = {0: (f"/{slug}/", os.path.join(PUB, slug.replace("/", os.sep), "index.html"))}
    for idx, s in enumerate(ordered_starts, start=2):
        href = f"/{slug}/{idx}/"
        f = os.path.join(PUB, slug.replace("/", os.sep), str(idx), "index.html")
        m[s] = (href, f)
    return m


def rewrite(url, html, slug, page_map):
    soup = BeautifulSoup(html, "html.parser")
    for b in soup.find_all("base"):
        b.decompose()

    def handle(val):
        if not val:
            return None
        raw = val.strip()
        if raw.startswith(("data:", "mailto:", "tel:", "javascript:", "#")):
            return None
        abs_url, frag = urldefrag(urljoin(url, raw))
        if not crawl.is_same_host(abs_url):
            return None
        if crawl.is_asset_url(abs_url):
            crawl.download_asset(abs_url)
            return crawl.asset_local_href(abs_url) + (("#" + frag) if frag else "")
        p = urlparse(abs_url)
        q = parse_qs(p.query)
        # pager link of THIS category: path is the category root + has start=
        cat_path = p.path.rstrip("/")
        is_cat_root = cat_path in (f"/index.php/{slug}", f"/{slug}")
        if is_cat_root and "start" in q:
            sval = int(q["start"][0])
            if sval in page_map:
                return page_map[sval][0]
            return page_map[0][0]
        if is_cat_root:  # category root without start -> page 1
            return page_map[0][0]
        if "format=feed" in p.query or "tmpl=component" in p.query or "print=1" in p.query:
            return None  # leave; handled elsewhere / not a content page
        if crawl.want_page(abs_url):
            return crawl.page_local_href(abs_url) + (("#" + frag) if frag else "")
        return None

    for tag, attr in [("a", "href"), ("link", "href"), ("script", "src"),
                      ("img", "src"), ("source", "src"), ("iframe", "src")]:
        for el in soup.find_all(tag):
            v = el.get(attr)
            if v:
                nv = handle(v)
                if nv is not None:
                    el[attr] = nv
    return str(soup)


def main():
    slugs = find_paginated_categories()
    print("Paginated categories:", slugs)
    for slug in slugs:
        html1, ordered = discover_starts(slug)
        if html1 is None:
            print(f"  ! could not fetch {slug}")
            continue
        page_map = build_page_map(slug, ordered)
        total = len(page_map)
        print(f"\n=== {slug}: {total} pages (starts={ordered}) ===")
        # page 1
        out1 = rewrite(f"{BASE}/index.php/{slug}", html1, slug, page_map)
        href1, file1 = page_map[0]
        os.makedirs(os.path.dirname(file1), exist_ok=True)
        open(file1, "w", encoding="utf-8").write(out1)
        print(f"  page1 -> {href1}")
        # other pages
        for s in ordered:
            href, fpath = page_map[s]
            r = crawl.fetch(f"{BASE}/index.php/{slug}?start={s}")
            if r is None or r.status_code != 200:
                print(f"  ! fetch fail start={s}")
                continue
            out = rewrite(f"{BASE}/index.php/{slug}?start={s}", r.text, slug, page_map)
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            open(fpath, "w", encoding="utf-8").write(out)
            print(f"  page  -> {href}")
    print("\nDone.")


if __name__ == "__main__":
    main()
