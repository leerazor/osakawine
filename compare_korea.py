"""Match verified Korean retail offers against Takamura's catalog."""
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import argparse
import json
import re

from lxml import html

from collect import node_text, read_json, save, volume
from compare import GENERIC, PACK_COUNT, japanese_identity, recheck_identity


STORES = {'dailyshot.co': 'dailyshot', 'gooddealwine.store': 'gooddeal', 'm.kihya.com': 'kihya'}
YEAR = re.compile(r'\b(?:19|20)\d{2}\b')
NON_VINTAGE = re.compile(r'\bN[.\s-]*V\b|논\s*빈티지|논빈', re.I)
PACK = re.compile(r'(?:[2-9]|\d{2,})\s*(?:병|팩\s*세트|bottles?\b)|\d\s*종\s*세트|묶음|패키지|bundle|gift\s*set|vertical\s*set|\s\+\s', re.I)
CLOSED = re.compile(r'^\s*\[(?:공동구매\s*)?(?:마감|종료|품절)\s*\]|^품절$', re.I)
DIRECT_INCLUDED = re.compile(r'세금\s*(?:및|과|·|와|,|/|\+)\s*(?:국제\s*)?배송비\s*(?:가\s*)?(?:모두\s*)?포함|관부가세\s*및\s*(?:국제\s*)?배송비\s*(?:가\s*)?포함')
STYLE = {'레드': 'red', '화이트': 'white', '로제': 'rose', '스파클링': 'sparkling',
         '샴페인': 'sparkling', '오렌지': 'orange', '디저트': 'dessert', '주정강화': 'dessert'}
NAME_ALIASES = {
    frozenset({'sylvain', 'pataille', 'bourgogne', 'pinot', 'noir'}):
        frozenset({'sylvain', 'pataille', 'bourgogne', 'rouge'}),
}
LABELLED_VINEYARD = re.compile(r'엉\s*클레멍조|엉\s*클레망조|앙\s*클레망조|라\s*몽타뉴|끌로\s*뒤\s*샤또')


def local_date():
    return datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()


def clean_title(value):
    value = re.sub(r'^\s*(?:(?:\[[^]]+\])\s*)+', '', str(value or ''))
    return re.sub(r'\s+', ' ', value).strip()


def year_of(*values):
    candidates = {year for value in values if value for year in YEAR.findall(value)}
    if len(candidates) == 1:
        return next(iter(candidates))
    if not candidates and any(value and NON_VINTAGE.search(value) for value in values):
        return 'NV'
    return None


def product_schema(doc):
    for script in doc.xpath('//script[@type="application/ld+json"]/text()'):
        try:
            record = json.loads(script)
        except ValueError:
            continue
        if isinstance(record, dict) and record.get('@type') == 'Product':
            return record
    return {}


def next_product(doc):
    value = doc.xpath('string(//script[@id="__NEXT_DATA__"])')
    try:
        queries = json.loads(value)['props']['pageProps']['dehydratedState']['queries']
        return next(query['state']['data'] for query in queries
                    if 'getItemDetailsByTopProducts' in query['queryKey'])
    except (KeyError, TypeError, ValueError, StopIteration):
        return {}


def amount(value):
    match = re.fullmatch(r'([\d,]+)(?:\.0+)?', str(value or ''))
    return int(match[1].replace(',', '')) if match else None


def style_of(value):
    return next((style for text, style in STYLE.items() if text in value), None)


def product_info(store, doc, schema):
    offers = schema.get('offers') or {}
    if not isinstance(offers, dict) or (store != 'dailyshot' and offers.get('priceCurrency') != 'KRW'):
        return None
    name = str(schema.get('name') or '')
    value = amount(offers.get('price') or offers.get('lowPrice'))
    item_label = name
    countable = False
    quantity = None
    note = ''
    fields = {}
    if store == 'dailyshot':
        item = next_product(doc)
        if not item or item.get('category_name') != '와인' or item.get('is_not_expose_to_app'):
            return None
        en = clean_title(item.get('en_name'))
        item_label = str(item.get('name') or '')
        name = item_label or name
        item_tag = str(item.get('name_tag') or '')
        tag_year = re.match(r'^\s*((?:19|20)\d{2})\s*(?:빈티지|$)', item_tag)
        if not tag_year:
            tag_year = re.match(r'^\s*\[((?:19|20)\d{2})\]', item_label)
        if tag_year and year_of(en, clean_title(name)) not in (None, tag_year[1]):
            return None
        fields = {field['label']: str(field.get('value') or '') for field in item.get('information', []) if field.get('label')}
        live_price = amount(item.get('price'))
        if not live_price or (LABELLED_VINEYARD.search(item_tag) and not LABELLED_VINEYARD.search(clean_title(name))):
            return None
        if offers.get('priceCurrency') != 'KRW' and not doc.xpath('//*[not(self::script)][normalize-space(.)=$compact or normalize-space(.)=$spaced]',
                                                                compact=f'{live_price:,}원', spaced=f'{live_price:,} 원'):
            return None
        value = live_price
        stock = 'out' if item.get('status') not in (0, 4) or item.get('stock') == 0 or CLOSED.search(item_label) or CLOSED.search(str(item.get('delivery_notice') or '')) else 'available'
        quantity = amount(item.get('stock')) if stock == 'available' else 0
        direct = bool(item.get('is_cross_border_shopping') or item.get('service_type') == 6)
        # Pick-up prices are the seller's display price. For imports, use an
        # all-in amount only when the selected offer makes that explicit.
        proof = ' '.join(str(item.get(key) or '') for key in ('notice', 'owner_comment'))
        countable = not direct or bool(DIRECT_INCLUDED.search(proof))
        note = '' if countable else '직구 세금·배송비 포함 여부 미확인'
        method = '한국 직구' if direct else '국내 픽업'
        wine_type = style_of(str(item.get('subcategory_name') or ''))
    elif store == 'gooddeal':
        en = clean_title(doc.xpath('string((//h1/ancestor::div[contains(@class,"product-info")][last()]//*[contains(@class,"liquid")]/p)[1])'))
        if not en:
            en = clean_title(doc.xpath('string((//div[contains(@class,"product-info__block-item")]/div[contains(@class,"liquid")]/p)[1])'))
        fields = {node_text(node): node_text(node.getparent()).removeprefix(node_text(node)).strip()
                  for node in doc.xpath('//*[contains(@class,"gd-profile__label")]')}
        stock = 'available' if str(offers.get('availability', '')).endswith('/InStock') else 'out'
        badges = {node_text(node) for node in doc.xpath('//*[contains(@class,"gd-product-badge--")]')}
        if stock == 'available' and badges & {'By Request', '공동구매'}:
            stock = 'request'
        countable = any(DIRECT_INCLUDED.search(text) for text in doc.xpath('//*[normalize-space(text())="세금 및 배송비 포함"]/text()'))
        note = '' if countable else '직구 세금·배송비 포함 여부 미확인'
        method = '직구 세금·배송비 포함' if countable else '한국 직구'
        wine_type = style_of(fields.get('타입', ''))
    else:
        en = clean_title(doc.xpath('string(//*[@id="product_englishname"])'))
        delivery_fields = doc.xpath('//dt[normalize-space(.)="배송비"]')
        offer_text = node_text(delivery_fields[0].getparent()) if delivery_fields else ''
        direct = bool(re.search(r'해외\s*직구|세금포함|세금별도', name + ' ' + doc.xpath('string(//title)')))
        pickup = not direct and doc.xpath('normalize-space(//*[@id="deliveryMethod"])') == '매장픽업'
        delivery = re.search(r'([\d,]+)\s*원', offer_text)
        no_delivery = bool(re.search(r'무료\s*배송|배송비\s*무료', offer_text))
        taxes = bool(re.search(r'세금\s*포함|관부가세\s*포함', name))
        direct_total = bool(direct and taxes and (no_delivery or delivery) and not re.search(r'이상|부터|착불|별도', offer_text))
        countable = pickup or direct_total
        if direct_total and value and delivery and not no_delivery:
            value += amount(delivery[1])
        note = '' if countable else '배송·세금 조건 미확인'
        method = '국내 픽업' if pickup else '직구 세금·배송비 포함' if direct_total else '한국 판매 상품'
        stock = 'available' if str(offers.get('availability', '')).endswith('/InStock') else 'out'
        wine_type = None
    title = clean_title(name)
    if not en or not re.search(r'[A-Za-z]{3}', en) or not value or PACK.search(item_label) or PACK.search(en):
        return None
    if CLOSED.search(name):
        stock = 'out'
    capacity = fields.get('용량', '')
    size = volume(capacity) if capacity else None
    if not size and capacity.isdecimal():
        size = int(capacity)
    return {'name': title, 'en': en, 'price': value, 'stock': stock, 'quantity': quantity, 'method': method,
            'total': countable, 'note': note, 'type': wine_type,
            'vintage': year_of(en, title, fields.get('빈티지')),
            'volume': size or volume(en + ' ' + title)}


def read_offer(url, source, checked_date):
    parsed = urlsplit(url)
    store = STORES.get(parsed.netloc)
    if not store or parsed.scheme != 'https':
        return None
    doc = html.fromstring(source, parser=html.HTMLParser(encoding='utf-8'))
    offer = product_info(store, doc, product_schema(doc))
    if not offer:
        return None
    return {**offer, 'url': url, 'store': store, 'date': checked_date}


def market_identity(title, style):
    title = re.sub(r'\b(?:1er|1re)\s+cru\b', 'premier cru', title, flags=re.I)
    title = re.sub(r'\bvieilles?\s+vignes?\b|\bV\.\s*V\.(?=\W|$)', 'vieilles vignes', title, flags=re.I)
    tokens = recheck_identity(title, style)
    tokens -= {'bottle', 'giftbox', 'import', 'aoc', 'aop', 'doc', 'docg', 'igt'}
    return NAME_ALIASES.get(tokens, tokens)


def candidate_index(records):
    by_identity = defaultdict(list)
    for offer in records:
        for style in {offer['type'], 'sparkling'}:
            tokens = market_identity(offer['en'], style)
            if len(tokens) >= 2 and tokens - GENERIC:
                by_identity[tokens].append(offer)
    return by_identity


def match_korean_prices(wine, offers):
    purchases = []
    refs = []
    for offer in offers:
        if offer['type'] and wine['type'] not in {'other', offer['type']}:
            continue
        if market_identity(wine['en'], wine['type']) != market_identity(offer['en'], wine['type']):
            continue
        left, right = wine['vintage'], offer['vintage']
        size, other_size = wine['volume'], offer['volume']
        if size and other_size and size != other_size:
            continue
        if left and right and left != right:
            if not (left.isdecimal() and right.isdecimal() and abs(int(left) - int(right)) <= 3):
                continue
        if left and left.isdecimal() and int(left) < 2010 and not right:
            continue
        notes = []
        if left != right or not left:
            notes.append('빈티지 차이' if left and right else '빈티지 미표기')
        if not (size and other_size):
            notes.append('용량 미표기')
        if offer['stock'] != 'available':
            notes.append('주문 후 공급처 재고 확인 또는 공동구매 조건' if offer['stock'] == 'request' else '품절')
        if not offer['total']:
            notes.append(offer['note'])
        with_notes = {**{key: offer[key] for key in ('name', 'en', 'price', 'stock', 'method', 'vintage', 'volume', 'url', 'store', 'date')},
                      'quantity': offer.get('quantity'),
                      'notes': notes}
        if notes:
            refs.append((len(notes), -int(bool(left) and left == right), offer['stock'] != 'available', offer['price'], with_notes))
        else:
            purchases.append(with_notes)
    if purchases:
        best = min(purchases, key=lambda offer: offer['price'])
        result = {'purchase': best}
        conditional = [choice[-1] for choice in refs if choice[-1]['stock'] == 'request' and
                       choice[-1]['vintage'] == best['vintage'] and choice[-1]['volume'] == best['volume'] and
                       choice[-1]['price'] < best['price']]
        if conditional:
            result['reference'] = min(conditional, key=lambda offer: offer['price'])
        return result
    if refs:
        return {'reference': min(refs, key=lambda choice: choice[:-1])[-1]}
    return None


def compare_sets(target, wines):
    singles = defaultdict(list)
    for wine in wines:
        if wine['type'] == 'set' or not wine['vintage'] or not wine['volume']:
            continue
        offer = wine.get('korea', {}).get('purchase')
        awine = wine.get('awine', {})
        if not offer and awine.get('status') == 'exact' and awine.get('stock') == 'available':
            offer = {**awine, 'store': 'awine'}
        singles[japanese_identity(wine['jp'])].append((wine['vintage'], wine['volume'], offer))
    for wine in target:
        if wine['type'] != 'set' or not wine['pack']:
            continue
        title = wine['jp']
        names = re.split(r'\s*[&＋+]\s*', title)
        if len(names) == 1:
            if not wine['vintage'] or not PACK_COUNT.search(title) or re.search(r'飲み比べ|詰め合わせ|おすすめ|厳選|計\s*\d+本', title):
                continue
            counts = [wine['pack']]
        elif len(names) == wine['pack']:
            counts = [1] * len(names)
        else:
            continue
        components = []
        for name, count in zip(names, counts):
            candidates = singles[japanese_identity(name)]
            conditions = {(vintage, size) for vintage, size, _ in candidates}
            prices = [offer for _, _, offer in candidates if offer and (count == 1 or (offer.get('quantity') or 0) >= count)]
            if len(conditions) != 1 or not prices:
                break
            offer = min(prices, key=lambda row: row['price'])
            components.append({**offer, 'count': count})
        if len(components) == len(counts):
            wine['korea'] = {'purchase': {'price': sum(part['price'] * part['count'] for part in components),
                                         'date': min(part['date'] for part in components),
                                         'method': '동일 구성품 합계', 'components': components}}


def build(dataset, offers, details):
    wines = dataset['wines']
    target = [wine for wine in wines if not wine.get('awine')]
    index = candidate_index(offers)
    for wine in target:
        wine.pop('korea', None)
        if wine['type'] != 'set' and wine.get('en'):
            price = match_korean_prices(wine, index.get(market_identity(wine['en'], wine['type']), []))
            if price:
                wine['korea'] = price
    compare_sets(target, wines)
    stats = Counter('purchase' if 'purchase' in wine['korea'] else 'reference' for wine in target if wine.get('korea'))
    dataset['meta']['korea'] = {'date': local_date(), 'targets': len(target), 'purchase': stats['purchase'],
                                'reference': stats['reference'], 'offers': len(offers), **details}
    return dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--offers', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = read_json(args.offers, {})
    result = build(read_json(args.snapshot, {}), source['offers'], source.get('details', {}))
    save(args.output, result)
    print(json.dumps(result['meta']['korea'], ensure_ascii=False))


if __name__ == '__main__':
    main()
