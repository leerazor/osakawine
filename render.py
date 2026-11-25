"""Package the dashboard as one HTML file that works without a server."""
from pathlib import Path
import argparse
import json
import math

from wine_names import add_wine_names

ROOT = Path(__file__).resolve().parent
WINE_SEARCHER_PRICES = ROOT / 'wine_searcher_prices.json'
OVERSEAS_PRICES = ROOT / 'overseas_prices.json'


def add_wine_searcher_prices(data, price_file):
    if not price_file.is_file():
        return
    prices = json.loads(price_file.read_text(encoding='utf-8'))
    recheck = prices.get('recheck', {})
    queried = set(recheck.get('queried', ()))
    matched_from = recheck.get('matchedFrom', {})
    checked = available = 0
    for wine in data['wines']:
        row = prices['results'].get(wine['id'])
        if row is None or (wine['vintage'], wine['volume']) != (row['vintage'], row['volume']):
            continue
        price = row['usd']
        if price is not None and (type(price) not in (int, float) or not math.isfinite(price) or price <= 0):
            raise ValueError(f"Invalid Wine-Searcher price for {wine['id']}")
        if price is not None and (wine['type'] == 'set' or wine['vintage'] is None or wine['volume'] is None):
            raise ValueError(f"Unmatched Wine-Searcher price for {wine['id']}")
        wine['wineSearcherUsd'] = price
        if wine['id'] in queried:
            wine['wineSearcherRechecked'] = True
        if wine['id'] in matched_from:
            wine['wineSearcherMatchedFrom'] = matched_from[wine['id']]
        checked += 1
        available += price is not None
    data['meta']['wineSearcher'] = {'date': prices['date'], 'checked': checked, 'available': available}
    if recheck:
        data['meta']['wineSearcher']['rechecked'] = sum(wine.get('wineSearcherRechecked', False) for wine in data['wines'])
        data['meta']['wineSearcher']['matched'] = sum('wineSearcherMatchedFrom' in wine for wine in data['wines'])


def add_overseas_prices(data, price_file):
    if not price_file.is_file():
        return
    lookup = json.loads(price_file.read_text(encoding='utf-8'))
    for wine in data['wines']:
        row = lookup['results'].get(wine['id'])
        if row is None or wine['type'] == 'set' or (wine['vintage'], wine['volume']) != (row['vintage'], row['volume']):
            continue
        for price in row['prices']:
            amount = price['amount']
            if type(amount) not in (int, float) or not math.isfinite(amount) or amount <= 0 or price['currency'] not in {'USD', 'EUR'}:
                raise ValueError(f"Invalid overseas price for {wine['id']}")
        wine['overseasPrices'] = row['prices']
    data['meta']['overseasPriceDate'] = lookup['date']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wine-searcher-prices', type=Path, default=WINE_SEARCHER_PRICES)
    parser.add_argument('--overseas-prices', type=Path, default=OVERSEAS_PRICES)
    args = parser.parse_args()
    data = add_wine_names(json.loads(args.data.read_text(encoding='utf-8')))
    add_wine_searcher_prices(data, args.wine_searcher_prices)
    add_overseas_prices(data, args.overseas_prices)
    embedded_json = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    page = (ROOT / 'page.html').read_text(encoding='utf-8').replace('/* DASHBOARD_STYLES */', (ROOT / 'styles.css').read_text(encoding='utf-8')).replace('/* DASHBOARD_SCRIPT */', (ROOT / 'app.js').read_text(encoding='utf-8')).replace('/* DASHBOARD_DATA */', embedded_json)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding='utf-8')


if __name__ == '__main__':
    main()
