"""Collect Takamura Plus catalog and authoritative product fields for offline shopping research."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import json
import re
import subprocess
import unicodedata

from lxml import etree, html

TAKAMURA = 'https://takamuraplus.jp'
AWINE = 'https://awine.kr'
LIST_URL = TAKAMURA + '/shopbrand/all_items/'
TITLE_YEAR = re.compile(r'\[\s*((?:18|19|20)\d{2})\s*\]')
SIZE = re.compile(r'(\d+(?:\.\d+)?)\s*(m[lL]|[lL])(?![a-zA-Z])')
CLASS = "contains(concat(' ',normalize-space(@class),' '), ' {} ')"
NOW = datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()


def node_text(node):
    return ' '.join(node.text_content().split()) if node is not None else ''


def volume(value):
    value = unicodedata.normalize('NFKC', value).lower()
    match = SIZE.search(value.replace(',', '.'))
    if match:
        amount, unit = match.groups()
        return round(float(amount) * (1000 if unit.lower() == 'l' else 1))
    if re.search(r'ダブル\s*マグナム|더블\s*(?:매그넘|마그넘)|double\s+magnum', value):
        return 3000
    if re.search(r'マグナム|매그넘|마그넘|\bmagnum\b', value):
        return 1500
    if re.search(r'ハーフ|하프\s*보틀|half[ -]bottle', value):
        return 375
    return None


def fetch(url):
    command = ['curl', '--fail', '--silent', '--show-error', '--location', '--compressed',
               '--proto', '=https', '--max-time', '16', '--retry', '1', '--retry-delay', '1', url]
    response = subprocess.run(command, capture_output=True, check=False)
    if response.returncode:
        raise OSError(response.stderr.decode(errors='replace').strip())
    return response.stdout


def read_json(path, default):
    return json.loads(path.read_text()) if path.is_file() else default


def save(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(path)


def catalog_page(page):
    url = LIST_URL if page == 1 else f'{LIST_URL}page{page}/order/'
    root = html.fromstring(fetch(url))
    count = re.search(r'全\s*([\d,]+)\s*件', root.text_content())
    rows = []
    for card in root.xpath(f'//*[{CLASS.format("category-list-detail")}]'):
        link = card.xpath(f'.//p[{CLASS.format("name")}]/a')[0]
        sku = re.search(r'/shopdetail/(\d+)', link.get('href')).group(1)
        price = re.search(r'([\d,]+)\s*円', card.xpath(f'string(.//em[{CLASS.format("price")}])'))
        rows.append({'id': sku, 'jp': node_text(link), 'yen': int(price[1].replace(',', '')) if price else None,
                     'onlineStock': 'out' if re.search(r'品切れ|売り切れ|SOLD OUT', node_text(card), re.I) else None,
                     'url': f'{TAKAMURA}/shopdetail/{sku}/'})
    if not count or not rows:
        raise ValueError(f'catalog layout or empty result on page {page}')
    return {'count': int(count[1].replace(',', '')), 'rows': rows}


def details(url):
    root = html.fromstring(fetch(url))
    def field(name):
        nodes = root.xpath(f'//*[contains(@class,"tws-td_{name}")]')
        return node_text(nodes[0]) if nodes else ''
    def meta(prop):
        return root.xpath(f'string(//meta[@property="{prop}"]/@content)')
    title = root.xpath('//h1')[0] if root.xpath('//h1') else None
    price = meta('product:price:amount')
    if (title is None or not price.isdecimal()) and root.xpath('//form[@name="check"]'):
        return {'onlineStock': 'member'}
    if title is None or not price.isdecimal():
        raise ValueError('product title or price missing')
    cart = root.xpath('//*[contains(@class,"item-soldout") or contains(@class,"soldout") or contains(@class,"btn-add-cart") or contains(@class,"add-cart")]')
    stock = 'available' if root.xpath(f'//a[{CLASS.format("btn-basket")}]') else None
    for node in cart:
        value = node_text(node)
        if re.fullmatch(r'(品切れ|売り切れ|SOLD OUT|再入荷のお知らせ|再入荷お知らせ)(です)?', value, re.I):
            stock = 'out'
    return {'jp': node_text(title), 'yen': int(price), 'en': field('name'),
            'areaJP': field('sanchi'), 'areaEN': field('region'), 'producerJP': field('producer'),
            'volume': volume(field('capacity')), 'onlineStock': stock}


def url_locations(body):
    return etree.fromstring(body).xpath('//*[local-name()="loc"]/text()')


def catalog_awine(cache, workers):
    indexes = [str(url) for url in url_locations(fetch(f'{AWINE}/sitemap.xml'))
               if re.fullmatch(r'https://awine\.kr/wine-sitemap\d*\.xml', url)]
    results = run_batch(indexes, lambda url: url_locations(fetch(url)), workers, cache, 'AWINE sitemaps')
    return sorted({str(url) for page in results.values() for url in page if url.startswith(AWINE + '/wine/')})


def parse_awine(url):
    root = html.fromstring(fetch(url), parser=html.HTMLParser(encoding='utf-8'))
    headings = root.xpath('//main//h1[@id="kor_title"]')
    if not headings:
        raise ValueError('AWINE product name missing')
    section = headings[0].getparent()
    jp = node_text(headings[0])
    en = section.xpath('string(h2[@id="eng_title"])').strip()
    schema = {}
    for node in root.xpath('//script[@type="application/ld+json"]'):
        try:
            candidate = json.loads(node.text or '{}')
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and candidate.get('@type') == 'Product':
            schema = candidate
            break
    fields = {item.get('name'): str(item.get('value') or '') for item in schema.get('additionalProperty', []) if isinstance(item, dict)}
    price_box = section.xpath('.//p[@id="price"]')
    amounts = [int(value.replace(',', '')) for value in re.findall(r'([\d,]+)\s*원', node_text(price_box[0]) if price_box else '')]
    offer = schema.get('offers', {})
    structured = str(offer.get('price') or '') if isinstance(offer, dict) else ''
    price = int(structured) if structured.isdecimal() and int(structured) in amounts else next(iter(amounts), None)
    status = ' '.join(section.xpath(f'.//*[{CLASS.format("stock_status")}]//text()'))
    buttons = ' '.join(node_text(button) for button in section.xpath('.//button'))
    stock = ('out' if re.search(r'품절|입고 알림', status + ' ' + buttons) else
             'available' if '픽업' in status or '장바구니 담기' in buttons else 'unknown')
    label = en + ' ' + jp
    pack = re.search(r'(?:^|\D)([2-9]|[1-9]\d)\s*(?:병\s*(?:세트|묶음)|본\s*세트)', label, re.I)
    capacity = next((value for key, value in fields.items() if key and re.search(r'용량|capacity|volume', key, re.I)), '')
    year = re.search(r'(?<!\d)(?:18|19|20)\d{2}(?!\d)', label)
    vintage = year[0] if year else ('NV' if re.search(r'\bN[.\s-]*V\b|논\s*빈티지', label, re.I) else None)
    brand = schema.get('brand') or {}
    return {'url': url, 'name': jp, 'en': en, 'price': price, 'stock': stock, 'vintage': vintage,
            'volume': volume(label) or volume(capacity), 'pack': bool(pack), 'date': NOW,
            'brand': brand.get('name', '') if isinstance(brand, dict) else str(brand),
            'wineType': fields.get('와인타입', ''), 'area': fields.get('생산지역', '')}


def run_batch(keys, task, workers, path, label, limit=None):
    values = read_json(path, {})
    pending = [k for k in dict.fromkeys(keys) if str(k) not in values][:limit]
    print(f'{label}: {len(values)} cached, {len(pending)} to fetch', flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(task, key): str(key) for key in pending}
        errors = 0
        for finished, future in enumerate(as_completed(futures), 1):
            key = futures[future]
            try:
                values[key] = future.result()
            except (OSError, etree.LxmlError, ValueError, IndexError, AttributeError) as exc:
                errors += 1
                if errors <= 10:
                    print(f'  {key}: {exc}', flush=True)
            if finished % 50 == 0:
                save(path, values)
                print(f'{label}: {finished}/{len(pending)}, {errors} failed', flush=True)
    save(path, values)
    print(f'{label}: {len(values)} saved, {errors} failed this run', flush=True)
    return values


def collect_catalog(directory, workers):
    first = catalog_page(1)
    page_count = (first['count'] + len(first['rows']) - 1) // len(first['rows'])
    path = directory / 'takamura-pages.json'
    existing = read_json(path, {})
    existing['1'] = first
    save(path, existing)
    pages = run_batch(range(2, page_count + 1), lambda page: catalog_page(page), workers, path, 'Takamura catalog')
    rows = {row['id']: row for page in sorted(pages, key=int) for row in pages[page]['rows']}
    print('Takamura expected / pages / unique:', first['count'], len(pages), len(rows), flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['catalog', 'takamura', 'awine-index', 'awine-details'])
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    if args.stage == 'catalog':
        collect_catalog(args.cache, args.workers)
    elif args.stage == 'takamura':
        pages = read_json(args.cache / 'takamura-pages.json', {})
        rows = {row['id']: row for page in sorted(pages, key=int) for row in pages[page]['rows']}
        priority = sorted(rows, key=lambda sku: (min(rows[sku]['yen'] or 0, 55000), sku), reverse=True)
        run_batch(priority, lambda sku: details(rows[sku]['url']), args.workers,
                  args.cache / 'takamura-details.json', 'Takamura details', args.limit)
    elif args.stage == 'awine-index':
        urls = catalog_awine(args.cache / 'awine-sitemaps.json', args.workers)
        save(args.cache / 'awine-urls.json', urls)
        print('AWINE unique wine URLs:', len(urls), flush=True)
    else:
        urls = read_json(args.cache / 'awine-candidates.json', [])
        run_batch(urls, lambda url: parse_awine(url), args.workers,
                  args.cache / 'awine-details.json', 'AWINE products', args.limit)


if __name__ == '__main__':
    main()
