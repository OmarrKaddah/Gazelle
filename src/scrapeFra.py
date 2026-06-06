import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urldefrag, unquote
import requests
from bs4 import BeautifulSoup

# Scrape FRA (Egyptian Financial Regulatory Authority) regulation PDFs.
# The listing at lc00-regulations links directly to PDFs on wp-content/uploads,
# paginated via a "Next" link. We follow that link rather than guessing the URL
# scheme, download each PDF into Documents/fra/, and write a provenance manifest.

BASE_URL = 'https://fra.gov.eg/en/lc00-regulations/'
OUT_DIR = Path('Documents/fra')
HEADERS = {'User-Agent': 'Mozilla/5.0 (Gazelle research crawler)'}


def fetchHtml(url):
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    
    return resp.text


def parsePdfLinks(html, pageUrl):
    soup = BeautifulSoup(html, 'html.parser')
    out = []
    for a in soup.find_all('a', href=True):
        if a['href'].lower().split('?')[0].endswith('.pdf'):
            href = urljoin(pageUrl, a['href'])
            title = a.get_text(strip=True) or unquote(href.rsplit('/', 1)[-1])
            out.append((href, title))
    return out


def findNextUrl(html, pageUrl):
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.find_all('a', href=True):
        text = a.get_text(strip=True).lower()
        if a.get('rel') == ['next'] or 'next' in text or '»' in text:
            return urljoin(pageUrl, a['href'])
    return None


def safeName(url):
    name = unquote(url.rsplit('/', 1)[-1])
    return re.sub(r'[^\w.\-؀-ۿ]+', '_', name)


def downloadPdf(url, dest):
    resp = requests.get(url, headers=HEADERS, timeout=120)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return len(resp.content)


def scrapeFra(maxPages=None):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    seenPdfs = set()
    visitedPages = set()
    url = BASE_URL
    page = 1
    while url and (maxPages is None or page <= maxPages):
        base = urldefrag(url)[0]
        if base in visitedPages:
            break
        visitedPages.add(base)
        html = fetchHtml(url)
        links = parsePdfLinks(html, url)
        print(f'[fra] page {page}: {len(links)} pdf links  ({url})', flush=True)
        for href, title in links:
            if href in seenPdfs:
                continue
            seenPdfs.add(href)
            fname = safeName(href)
            dest = OUT_DIR / fname
            entry = {'url': href, 'title': title, 'filename': fname, 'sourcePage': page}
            if dest.exists():
                entry['status'] = 'exists'
            else:
                try:
                    entry['bytes'] = downloadPdf(href, dest)
                    entry['status'] = 'ok'
                except Exception as e:
                    entry['status'] = f'fail: {str(e)[:120]}'
                time.sleep(0.5)
            manifest.append(entry)
            print(f'  {entry["status"]:>8}  {fname}', flush=True)
        url = findNextUrl(html, url)
        page += 1
    (OUT_DIR / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    ok = sum(1 for m in manifest if m['status'] == 'ok')
    exists = sum(1 for m in manifest if m['status'] == 'exists')
    print(f'[fra] done: {len(manifest)} pdfs ({ok} new, {exists} already present), '
          f'manifest -> {OUT_DIR}/manifest.json', flush=True)
    return manifest
