import json
import re
import time
from pathlib import Path
from urllib.parse import urldefrag, unquote, urlparse
from playwright.sync_api import sync_playwright



SEED_URLS = [
    'https://www.cbe.org.eg/en/laws-regulations/regulations/overview',
]
OUT_DIR = Path('Documents/cbe')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')


def isPdf(url):
    u = url.lower().split('?')[0]
    if '.png' in u or '.jpg' in u or '.jpeg' in u or '.gif' in u or '.svg' in u:
        return False   # diagram images sometimes carry a trailing .pdf
    return u.endswith('.pdf') or '/-/media/' in u


def bumpPageNo(url):
    m = re.search(r'pageNo=(\d+)', url)
    if not m:
        return None
    return url[:m.start()] + f'pageNo={int(m.group(1)) + 1}' + url[m.end():]


def isRegLink(url):

    return '/laws-regulations/' in url.lower() and not isPdf(url)


def harvestLinks(page):

    return page.eval_on_selector_all('a[href]', 'els => els.map(e => e.href)')


def safeName(url):
    name = unquote(urlparse(url).path.rsplit('/', 1)[-1]) or 'doc'
    if not name.lower().endswith('.pdf'):
        name += '.pdf'
    return re.sub(r'[^\w.\-؀-ۿ]+', '_', name)


def looksBlocked(title):
    t = title.lower()
    return 'rejected' in t or 'denied' in t or 'forbidden' in t or title == ''


def downloadPdf(ctx, url, dest):
    resp = ctx.request.get(url, timeout=120000)
    if resp.status != 200:

        return None, str(resp.status)
    body = resp.body()
    if not body.startswith(b'%PDF'):

        return None, 'not-pdf'
    dest.write_bytes(body)
    return len(body), '200'


def harvestPdfUrls(page, seeds, maxDepth, maxPages=400):


    pdfUrls = set()
    visited = set()
    queue = [(u, 0) for u in seeds]
    while queue and len(visited) < maxPages:
        url, depth = queue.pop(0)
        base = urldefrag(url)[0]

        if base in visited:

            continue
        visited.add(base)
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(2500)
        except Exception as e:
            print(f'[cbe] LOAD FAIL {url}: {str(e)[:120]}', flush=True)
            continue
        title = page.title()
        links = harvestLinks(page)

        pdfs = [u for u in links if isPdf(u)]

        regs = [u for u in links if isRegLink(u)]
        newPdfs = [u for u in pdfs if u not in pdfUrls]
        pdfUrls.update(pdfs)
        flag = 'BLOCKED ' if looksBlocked(title) else ''
        print(f'[cbe] {flag}{title[:50]!r} <- {url[:90]}  ({len(pdfs)} pdfs, {len(regs)} reg-links)', flush=True)
        # next page of a paginated list, only if this page still yielded new PDFs
        if 'pageNo=' in base and newPdfs:
            nxt = bumpPageNo(url)
            if nxt:
                queue.append((nxt, depth))
        if depth < maxDepth:
            for r in regs:
                queue.append((r, depth + 1))
    return pdfUrls


def scrapeCbe(headless=True, maxDepth=1, seeds=SEED_URLS):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:

        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(user_agent=UA, viewport={'width': 1366, 'height': 900})
        page = ctx.new_page()

        pdfUrls = harvestPdfUrls(page, seeds, maxDepth)
        print(f'[cbe] harvested {len(pdfUrls)} unique pdf urls; downloading...', flush=True)

        manifest = []
        for url in sorted(pdfUrls):
            fname = safeName(url)

            dest = OUT_DIR / fname

            entry = {'url': url, 'filename': fname}
            if dest.exists():
                entry['status'] = 'exists'

            else:
                size, code = downloadPdf(ctx, url, dest)
                entry['status'] = 'ok' if size else f'fail:{code}'
                if size:
                    entry['bytes'] = size
                time.sleep(0.3)
            manifest.append(entry)
            print(f'  {entry["status"]:>10}  {fname}', flush=True)
        browser.close()


    (OUT_DIR / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    ok = sum(1 for m in manifest if m['status'] == 'ok')
    print(f'[cbe] done: {len(manifest)} pdfs ({ok} new), manifest -> {OUT_DIR}/manifest.json', flush=True)
    return manifest
