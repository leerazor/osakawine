"""Build the dashboard data and select AWINE product pages to verify."""
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit
import argparse
import json
import re
import unicodedata

from collect import NOW, TITLE_YEAR, read_json, save, takamura_volume

PRICE_RATE = {'krwPerYen': 8.4909, 'date': '2026-11-20',
              'url': 'https://kr.investing.com/currencies/jpy-krw-historical-data'}
WINE = re.compile(r'ワイン|シャンパ[ー�-]?ニュ|シャンパン|スパークリング|泡\s*[白赤ロ]|クレマン|カヴァ|フランチャコルタ|ペット\s*ナット')
NOT_WINE = re.compile(r'紙袋|ラッピング|ギフトボックス|保冷バッグ|水引|カレンダー|ワイングラス|コルク抜き|ワインオープナー|ワインセラー|グラス\s*[（(]|グラスセット|ワインチケット|頒布会チケット|テイスティングチケット|クール便|空き瓶')
NOT_GRAPE = re.compile(r'\(\s*(?:日本酒|焼酎|リキュール|ジン|ビール|グラッパ|ブランデー|ウイスキー|シードル|ジュース)\s*\)|(?:缶ビール|りんごジュース|ドリップバッグ)')
PACK_COUNT = re.compile(r'(\d+)\s*本\s*(?:入[り]?|セット|組|ケース)')
COUNTRIES = {
    'France': '프랑스', 'Italy': '이탈리아', 'Spain': '스페인', 'Germany': '독일',
    'Portugal': '포르투갈', 'Austria': '오스트리아', 'America': '미국', 'USA': '미국',
    'United States': '미국', 'Australia': '호주', 'New Zealand': '뉴질랜드', 'Japan': '일본',
    'Argentina': '아르헨티나', 'Chile': '칠레', 'South Africa': '남아공', 'Georgia': '조지아',
    'Hungary': '헝가리', 'Greece': '그리스', 'England': '영국', 'United Kingdom': '영국',
    'Canada': '캐나다', 'Switzerland': '스위스', 'Slovenia': '슬로베니아', 'Croatia': '크로아티아',
    'Romania': '루마니아', 'Bulgaria': '불가리아', 'Israel': '이스라엘', 'Lebanon': '레바논',
    'フランス': '프랑스', 'イタリア': '이탈리아', 'スペイン': '스페인', 'ドイツ': '독일',
    'ポルトガル': '포르투갈', 'アメリカ': '미국', 'オーストリア': '오스트리아',
    'オーストラリア': '호주', 'ニュージーランド': '뉴질랜드', '日本': '일본',
    '南アフリカ': '남아공', 'アルゼンチン': '아르헨티나', 'チリ': '칠레', 'イギリス': '영국',
}
VIVINO = {
    'Carruades de Lafite Rothschild': 'https://www.vivino.com/en/chateau-lafite-rothschild-carruades-de-lafite-pauillac/w/23793',
    'Vosne Romanee Les Hautes Maizieres Philippe Pacalet': 'https://www.vivino.com/en/philippe-pacalet-vosne-romanee-les-hautes-maizieres/w/13582893',
}
REGIONS = {'Champagne': '샹파뉴', 'Bordeaux': '보르도', 'Bourgogne': '부르고뉴',
           'Burgundy': '부르고뉴', 'Rhone': '론', 'Loire': '루아르', 'Alsace': '알자스',
           'Piedmont': '피에몬테', 'Piemonte': '피에몬테', 'Tuscany': '토스카나',
           'Toscana': '토스카나', 'California': '캘리포니아', 'Napa Valley': '나파 밸리',
           'シャンパーニュ': '샹파뉴', 'ボルドー': '보르도', 'ブルゴーニュ': '부르고뉴',
           'ローヌ': '론', 'ロワール': '루아르', 'アルザス': '알자스'}
FUNCTION_WORDS = {'de', 'del', 'des', 'du', 'di', 'da', 'la', 'le', 'les', 'l', 'the', 'and',
                  'et', 'e', 'd', 'a', 'wine', 'nv', 'ml', '750ml'}
PRODUCER_PREFIXES = {'chateau', 'domaine', 'estate', 'winery', 'cellars', 'bodega', 'bodegas'}
DISTINCT_PREFIXES = {'leroy', 'drouhin', 'faiveley'}
GENERIC = {'chateau', 'domaine', 'brut', 'cuvee', 'champagne', 'bourgogne', 'bordeaux', 'rouge',
           'blanc', 'rose', 'grand', 'premier', 'cru', 'barolo', 'chianti', 'riserva', 'reserve',
           'cabernet', 'sauvignon', 'chardonnay', 'pinot', 'noir', 'riesling', 'bottle', 'merlot'}
RECHECK_DESCRIPTORS = {'tenuta', 'dell', 'delle', 'della', 'dello', 'millesime', 'vintage', 'case', 'coffret'}
RECHECK_SPARKLING_DESCRIPTORS = {'champagne', 'brut'}
OLD_VINTAGE_CUTOFF = 2010
RECHECK_CANONICAL_NAMES = {
    frozenset({'ornellaia'}): frozenset({'ornellaia', 'bolgheri', 'superiore'}),
    frozenset({'coche', 'dury', 'bourgogne', 'blanc'}): frozenset({'coche', 'dury', 'bourgogne', 'chardonnay'}),
}
AWINE_STYLES = {'레드와인': 'red', '화이트와인': 'white', '로제와인': 'rose',
                '스파클링와인': 'sparkling', '샴페인': 'sparkling', '로제샴페인': 'sparkling',
                '오렌지와인': 'orange'}
UNBRACKETED_VINTAGE = re.compile(r'(?<=[ァ-ヺー])\.?((?:19|20)\d{2})(?=\s*[ァ-ヺー])')
NON_VINTAGE = re.compile(r'(?<![A-Za-z])NV(?:(?![A-Za-z])|(?=Lot\b))|ノン\s*ヴィンテージ', re.I)


def takamura_vintage(title, kind):
    match = TITLE_YEAR.search(title)
    if match:
        return match[1]
    if NON_VINTAGE.search(title):
        return 'NV'
    if kind not in ('set', 'other'):
        match = UNBRACKETED_VINTAGE.search(title.split('※', 1)[0])
        if match:
            return match[1]
    return None


def ascii_text(value):
    value = unicodedata.normalize('NFKD', value.lower())
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return value.replace('œ', 'oe').replace('æ', 'ae').replace('’', "'")


def norm_words(name):
    name = ascii_text(name)
    name = re.sub(r'\([^)]*(?:grand cru class[eé]|gift box|case included)[^)]*\)', ' ', name)
    name = re.sub(r'\b(?:non[ -]vintage|n\.?v\.?|wine[- ]\d+)\b', ' ', name)
    name = re.sub(r"\b([dl])'", '', name)
    name = re.sub(r'\b(?:18|19|20)\d{2}\b|\b\d+(?:[.,]\d+)?\s*(?:ml|l)\b|\b(?:double\s+magnum|magnum|half[ -]bottle)\b', ' ', name)
    words = re.findall(r'[a-z]+[a-z0-9]*|[0-9]+', name)
    aliases = {'st': 'saint', 'ste': 'sainte', 'vieil': 'vieux'}
    words = [aliases.get(word, word) for word in words if word not in FUNCTION_WORDS]
    return tuple(words)



def identity_words(value):
    words = frozenset(norm_words(value))
    reduced = words - PRODUCER_PREFIXES
    if len(reduced) > 2 and reduced - GENERIC and not reduced & DISTINCT_PREFIXES:
        return reduced
    return words


def slug_name(url):
    slug = unquote(urlsplit(url).path.rstrip('/').rsplit('/', 1)[-1])
    parts = re.split(r'[가-힣ㄱ-ㅎㅏ-ㅣ]+', slug)
    return re.sub(r'-wine-\d+/?$', '', parts[-1]).strip('-').replace('-', ' ')


def label_type(title):
    if PACK_COUNT.search(title) or re.search(r'飲み比べ|ワイン\s*セット|ワインセット|詰め合わせ', title):
        return 'set'
    if re.search(r'甘口\s*(?:ワイン|\))|貴腐|酒精強化|アイスワイン|ポートワイン|マデイラ|シェリー|キナート|ヴェルモット', title):
        return 'dessert'
    if re.search(r'泡\s*[白赤ロ]|発泡|スパークリング|シャンパ[ー]?ニュ|シャンパン|クレマン|フランチャコルタ|カヴァ', title):
        return 'sparkling'
    if re.search(r'オレンジ\s*(?:ワイン|\))', title):
        return 'orange'
    if re.search(r'ロゼ\s*(?:ワイン|\))', title):
        return 'rose'
    if '赤ワイン' in title:
        return 'red'
    if '白ワイン' in title:
        return 'white'
    return 'other'


def looks_wine(title, detail):
    if (NOT_GRAPE.search(title) and not re.search(r'キナート|ヴェルモット', title)) or (NOT_WINE.search(title) and not re.search(r'赤ワイン|白ワイン|ロゼワイン|泡\s*[白ロ]|シャンパーニュ', title)):
        return False
    return bool(WINE.search(title) or PACK_COUNT.search(title) or detail.get('en') or re.search(r'混醸|ペティアン|ヴァン\s*ジョーヌ|ヴァン\s*ド\s*パイユ|ヴァン\s*ナチュレル', title))


def location(detail, title):
    pieces = [p.strip() for p in re.split(r'[/／>＞]', detail.get('areaJP', '') + '/' + detail.get('areaEN', '')) if p.strip()]
    country = next((COUNTRIES[p] for p in pieces if p in COUNTRIES), '')
    region = next((REGIONS[p] for p in pieces if p in REGIONS), '')
    areas = [part.strip() for part in re.split(r'[/／>＞]', detail.get('areaEN', '')) if part.strip()]
    if not region and len(areas) > 1 and areas[0] in COUNTRIES:
        region = areas[1]
    for clue, display in REGIONS.items():
        if not region and clue in title:
            region = display
    if not country and region in {'샹파뉴', '부르고뉴', '보르도', '론', '루아르', '알자스'}:
        country = '프랑스'
    if not country and region in {'피에몬테', '토스카나'}:
        country = '이탈리아'
    if not country and region in {'캘리포니아', '나파 밸리'}:
        country = '미국'
    return country, region


def catalog(cache):
    pages = read_json(cache / 'takamura-pages.json', {})
    details = read_json(cache / 'takamura-details.json', {})
    seen = {}
    for page in sorted(pages, key=int):
        for listing in pages[page]['rows']:
            seen.setdefault(listing['id'], listing)
    rows = []
    vivino = {identity_words(name): url for name, url in VIVINO.items()}
    for item in seen.values():
        d = details.get(item['id'], {})
        title = unicodedata.normalize('NFKC', d.get('jp') or item['jp'])
        if not looks_wine(title, d):
            continue
        wt = label_type(title)
        vintage = takamura_vintage(title, wt)
        country, region = location(d, title)
        pack = PACK_COUNT.search(title)
        en = d.get('en', '')
        rows.append({**item, 'jp': d.get('jp') or item['jp'], 'yen': d.get('yen', item['yen']),
                     'onlineStock': d.get('onlineStock') or item['onlineStock'], 'en': en,
                     'vivino': vivino.get(identity_words(en)),
                     'country': country, 'region': region, 'area': d.get('areaJP') or d.get('areaEN', ''),
                     'producer': d.get('producerJP', ''), 'vintage': vintage, 'type': wt,
                     'volume': takamura_volume(title, d.get('volume'), en), 'pack': int(pack[1]) if pack else None})
    member_count = sum(detail.get('onlineStock') == 'member' for detail in details.values())
    metadata = {'catalogTotal': pages.get('1', {}).get('count'), 'catalogPages': len(pages),
                'listingCount': len(seen), 'detailsCount': len(details) - member_count, 'wineCount': len(rows),
                'memberOnly': member_count, 'detailsUnavailable': len(seen) - len(details),
                'distinctListingCounts': sorted({page['count'] for page in pages.values()}),
                'checkedDate': NOW, 'fx': PRICE_RATE}
    return rows, metadata


def candidate_index(urls):
    by_token = defaultdict(list)
    candidates = []
    for url in urls:
        name = slug_name(url)
        words = identity_words(name)
        if not words or len(name) < 3:
            continue
        found = re.search(r'\b(?:18|19|20)\d{2}\b', name)
        vintage = found[0] if found else ('NV' if re.search(r'\bNV\b', name, re.I) else None)
        position = len(candidates)
        candidates.append((url, words, vintage))
        for word in words:
            by_token[word].append(position)
    return candidates, by_token


def candidate_urls(row, names, by_token):
    words = identity_words(row['en'])
    distinct = words - GENERIC
    if not distinct or row['type'] == 'set' or not words:
        return []
    rare = sorted(distinct, key=lambda word: len(by_token.get(word, [])))[:5]
    positions = {i for token in rare for i in by_token.get(token, [])}
    comparisons = []
    row_vintage = row['vintage']
    for pos in positions:
        url, official, vintage = names[pos]
        intersection = words & official
        if not (distinct & intersection):
            continue
        overlap = len(intersection) / len(words | official)
        if overlap < (0.63 if len(words) > 2 else 0.8):
            continue
        same = row_vintage is not None and row_vintage == vintage
        gap = abs(int(row_vintage) - int(vintage)) if row_vintage and vintage and row_vintage.isdecimal() and vintage.isdecimal() else 999
        comparisons.append((overlap, same, -gap, url))
    comparisons.sort(reverse=True)
    return [row[3] for row in comparisons[:4]]


def recheck_identity(title, wine_type):
    words = identity_words(title) - RECHECK_DESCRIPTORS
    if wine_type == 'sparkling':
        words -= RECHECK_SPARKLING_DESCRIPTORS
    if {'coche', 'dury'} <= words:
        words -= {'j', 'f'}
    return RECHECK_CANONICAL_NAMES.get(words, words)


def same_rechecked_wine(row, offer):
    actual_type = AWINE_STYLES.get(offer.get('wineType', '').replace(' ', ''))
    if actual_type and row['type'] in AWINE_STYLES.values() and actual_type != row['type']:
        return False
    left = recheck_identity(row['en'], row['type'])
    right = recheck_identity(offer['en'], row['type'])
    return bool(left - GENERIC and len(left) >= 2 and left == right)


def match_offer(row, candidates, *, recheck=False):
    words = identity_words(row['en'])
    if not words or not (words - GENERIC) or len(''.join(words)) < 5 or row['type'] == 'set':
        return None
    options = []
    for offer in candidates:
        same_wine = same_rechecked_wine(row, offer) if recheck else words == identity_words(offer['en'])
        if not same_wine or not offer['price'] or offer.get('pack') or re.search(r'병\s*세트', offer['name']):
            continue
        if (not offer['volume'] and re.search(r'매그넘|마그넘|더블매그넘|제로나봄|하프보틀|magnum|jeroboam|half bottle', offer['name'] + ' ' + offer['en'], re.I)):
            continue
        left, right = row['vintage'], offer['vintage']
        if recheck and not right and left and left.isdecimal() and int(left) < OLD_VINTAGE_CUTOFF:
            continue
        both_vintage = left is not None and right is not None
        year_equal = both_vintage and left == right
        gap = abs(int(left) - int(right)) if both_vintage and left.isdecimal() and right.isdecimal() else None
        if both_vintage and not year_equal and (gap is None or gap > 3):
            continue
        sizes = row['volume'], offer['volume']
        if all(sizes) and sizes[0] != sizes[1]:
            continue
        if any(size and size != 750 for size in sizes) and not all(sizes):
            continue
        reasons = []
        if not year_equal:
            reasons.append('빈티지 차이' if both_vintage else '빈티지 미표기')
        if not all(sizes):
            reasons.append('에이와인 750mL 가정' if sizes == (750, None) and year_equal else '용량 미표기')
        if offer['stock'] == 'out':
            reasons.append('에이와인 품절')
        status = 'exact' if not reasons else 'reference'
        estimated = year_equal and sizes == (750, None) and offer['stock'] == 'available'
        options.append(((status == 'exact', estimated, year_equal, offer['stock'] != 'out', gap is not None, -(gap or 0), offer['date']),
                        {**offer, 'status': status, 'estimated': estimated, 'notes': reasons}))
    if not options:
        return None
    return max(options, key=lambda choice: (choice[0], -choice[1]['price']))[1]



def japanese_identity(title):
    title = unicodedata.normalize('NFKC', title)
    title = re.sub(r'\(\s*(?:赤ワイン|白ワイン|ロゼワイン|オレンジ|泡\s*[白ロ]|追加\d|同梱).*$', '', title)
    title = re.sub(r'※.*$|【[^】]+】|\[[A-Z]\]|送料無料|限定特価|ベストセラー|木箱入り|箱入り|お一人様\d+セット限り', '', title)
    title = re.sub(r'(?:計\s*)?\d+\s*本\s*セット', '', title)
    return re.sub(r'[\s\[\]・、。]', '', title).casefold()


def match_sets(rows):
    singles = defaultdict(list)
    for row in rows:
        if row['type'] != 'set' and row['vintage']:
            singles[japanese_identity(row['jp'])].append(row)
    for wine in rows:
        if wine['type'] != 'set' or not wine['pack']:
            continue
        title = unicodedata.normalize('NFKC', wine['jp'])
        names = re.split(r'\s*[&＋+]\s*', title)
        if len(names) == 1:
            if not wine['vintage'] or re.search(r'飲み比べ|詰め合わせ|お?すすめ|おまかせ|厳選\s*セット|計\s*\d+本', title):
                continue
            counts = [wine['pack']]
        elif len(names) == wine['pack']:
            counts = [1] * len(names)
        else:
            continue
        components = []
        for name, count in zip(names, counts):
            candidates = singles[japanese_identity(name)]
            volumes = {item['volume'] for item in candidates if item['volume']}
            if len(volumes) > 1:
                break
            priced = [item['awine'] for item in candidates if item.get('awine')]
            if not priced:
                break
            offer = max(priced, key=lambda item: (item['status'] == 'exact', item['estimated'], -item['price']))
            components.append({**offer, 'count': count})
        if len(components) != len(counts):
            continue
        reference = any(part['status'] != 'exact' for part in components)
        estimated = reference and all(part['status'] == 'exact' or part['estimated'] for part in components)
        notes = list(dict.fromkeys(note for part in components for note in part['notes']))
        wine['awine'] = {'name': '', 'url': '', 'price': sum(part['price'] * part['count'] for part in components),
                         'vintage': None, 'volume': None, 'date': min(part['date'] for part in components),
                         'status': 'reference' if reference else 'exact', 'estimated': estimated,
                         'notes': notes, 'components': components}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['candidates', 'build'])
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--recheck-cache', type=Path)
    args = parser.parse_args()
    rows, metadata = catalog(args.cache)
    if args.stage == 'candidates':
        names, index = candidate_index(read_json(args.cache / 'awine-urls.json', []))
        planned = read_json(args.cache / 'awine-candidates.json', [])
        for row in rows:
            planned.extend(candidate_urls(row, names, index))
        urls = list(dict.fromkeys(planned))
        save(args.cache / 'awine-candidates.json', urls)
        print(f'{len(rows)} wines, {sum(bool(row["en"]) for row in rows)} with English title, {len(urls)} AWINE candidates')
        return
    by_name = defaultdict(list)
    details = read_json(args.cache / 'awine-details.json', {})
    for offer in details.values():
        by_name[identity_words(offer['en'])].append(offer)
    for row in rows:
        awine = match_offer(row, by_name[identity_words(row['en'])])
        if awine:
            row['awine'] = awine
    match_sets(rows)
    original_matches = {row['id'] for row in rows if row.get('awine')}
    if args.recheck_cache:
        plan = read_json(args.recheck_cache / 'plan.json', {})
        if 'candidates' not in plan or 'target' not in plan:
            parser.error('--recheck-cache needs a plan generated by prepare_recheck.py')
        if plan.get('takamuraCheckedDate'):
            metadata['checkedDate'] = plan['takamuraCheckedDate']
        rechecked = read_json(args.recheck_cache / 'awine-details.json', {})
        for row in rows:
            if row.get('awine'):
                continue
            urls = plan['candidates'].get(row['id'], [])
            offer = match_offer(row, (rechecked[url] for url in urls if url in rechecked), recheck=True)
            if offer:
                row['awine'] = offer
        details.update(rechecked)
        metadata['awineRecheck'] = {'targets': len(plan['target']), 'candidatePages': len({
            url for urls in plan['candidates'].values() for url in urls}),
            'readPages': len(rechecked), 'date': max((offer['date'] for offer in rechecked.values()), default=NOW)}
        match_sets(rows)
        metadata['awineRecheck']['added'] = sum(bool(row.get('awine')) and row['id'] not in original_matches for row in rows)
    metadata['awinePages'] = len(details)
    metadata['exact'] = sum(row.get('awine', {}).get('status') == 'exact' for row in rows)
    metadata['reference'] = sum(row.get('awine', {}).get('status') == 'reference' for row in rows)
    metadata['sets'] = sum(row['type'] == 'set' for row in rows)
    metadata['pricedSets'] = sum(bool(row.get('awine', {}).get('components')) for row in rows)
    metadata['estimated'] = sum(bool(row.get('awine', {}).get('estimated')) for row in rows)
    save(args.output, {'meta': metadata, 'wines': rows})
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == '__main__':
    main()
