#!/usr/bin/env python3
"""
Phase 2: capture the print views (?tmpl=component&print=1) and RSS/Atom feeds
(?format=feed) that the main crawler skipped, save them as static files, and
rewrite all references in the already-saved HTML to those static paths.
Run after crawl.py.
"""
import os
import re
import html as htmllib
from urllib.parse import urljoin, urlparse, urldefrag, unquote, parse_qs

import crawl  # reuse helpers (import does not run main())
from bs4 import BeautifulSoup

PUB = crawl.OUT
BASE = crawl.BASE


def real_url_from_href(page_file_dir, href):
    """Resolve an href (possibly relative/root) against the live site."""
    raw = htmllib.unescape(href)
    # All our internal links are root-relative or absolute on the host.
    return urljoin(BASE + "/", raw)


def print_paths(url):
    """Map a print-view URL to (local_href, local_file)."""
    p = urlparse(url)
    path = p.path
    if path.startswith("/index.php"):
        rem = path[len("/index.php"):]
    else:
        rem = path
    rem = rem.strip("/")
    base = rem if rem else "index"
    href = "/" + base + "/print/"
    f = os.path.join(PUB, base.replace("/", os.sep), "print", "index.html")
    return href, f


def feed_paths(url):
    """Map a feed URL to (local_href, local_file)."""
    p = urlparse(url)
    qs = parse_qs(p.query)
    ftype = qs.get("type", ["rss"])[0]
    path = p.path
    if path.startswith("/index.php"):
        rem = path[len("/index.php"):]
    else:
        rem = path
    rem = rem.strip("/")
    base = rem if rem else "home"
    href = "/feeds/" + base + "-" + ftype + ".xml"
    f = os.path.join(PUB, "feeds", (base + "-" + ftype + ".xml").replace("/", os.sep))
    return href, f


def localize_print_html(url, text):
    """Rewrite a fetched print page's asset/page links to local static paths."""
    soup = BeautifulSoup(text, "html.parser")
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
        q = urlparse(abs_url).query
        if "print=1" in q or "tmpl=component" in q:
            h, _ = print_paths(abs_url)
            return h
        if "format=feed" in q:
            h, _ = feed_paths(abs_url)
            return h
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
    # 1) Scan every saved HTML file for print/feed hrefs.
    href_re = re.compile(r'(?:href|src)="([^"]*(?:tmpl=component|format=feed)[^"]*)"')
    found = {}  # original_escaped_href -> real_url
    html_files = []
    for root, _, files in os.walk(PUB):
        for f in files:
            if f.endswith(".html"):
                p = os.path.join(root, f)
                html_files.append(p)
                txt = open(p, encoding="utf-8", errors="replace").read()
                for m in href_re.findall(txt):
                    if m not in found:
                        found[m] = real_url_from_href(os.path.dirname(p), m)

    print(f"Found {len(found)} distinct print/feed hrefs across {len(html_files)} pages.")

    # 2) Download each unique target and compute its new local href.
    mapping = {}  # original_escaped_href -> new_local_href
    seen_files = set()
    for esc_href, url in sorted(found.items()):
        q = urlparse(url).query
        is_feed = "format=feed" in q
        try:
            if is_feed:
                new_href, local_file = feed_paths(url)
            else:
                new_href, local_file = print_paths(url)
        except Exception as e:
            print(f"  ! map fail {url}: {e}")
            continue
        mapping[esc_href] = new_href
        if local_file in seen_files:
            continue
        seen_files.add(local_file)
        if os.path.exists(local_file):
            continue
        r = crawl.fetch(url)
        if r is None or r.status_code != 200:
            print(f"  FAIL {r.status_code if r else 'ERR'}: {url}")
            continue
        os.makedirs(os.path.dirname(local_file), exist_ok=True)
        if is_feed:
            with open(local_file, "wb") as fh:
                fh.write(r.content)
            print(f"  feed  -> {new_href}")
        else:
            out = localize_print_html(url, r.text)
            with open(local_file, "w", encoding="utf-8") as fh:
                fh.write(out)
            print(f"  print -> {new_href}")

    # 3) Replace all original hrefs in saved HTML with the new local hrefs.
    nfiles = 0
    for p in html_files:
        txt = open(p, encoding="utf-8", errors="replace").read()
        orig = txt
        for esc_href, new_href in mapping.items():
            if esc_href in txt:
                txt = txt.replace('"' + esc_href + '"', '"' + new_href + '"')
        if txt != orig:
            open(p, "w", encoding="utf-8").write(txt)
            nfiles += 1
    print(f"\nRewrote print/feed links in {nfiles} HTML files.")
    print(f"Saved {len(seen_files)} extra static files.")


if __name__ == "__main__":
    main()
