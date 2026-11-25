"""Package the dashboard as one HTML file that works without a server."""
from pathlib import Path
import argparse
import json
import math

from wine_names import add_wine_names

ROOT = Path(__file__).resolve().parent
WINE_SEARCHER_PRICES = ROOT / 'wine_searcher_prices.json'


def add_wine_searcher_prices(data, price_file):
    if not price_file.is_file():
        return
    prices = json.loads(price_file.read_text(encoding='utf-8'))
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
        checked += 1
        available += price is not None
    data['meta']['wineSearcher'] = {'date': prices['date'], 'checked': checked, 'available': available}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wine-searcher-prices', type=Path, default=WINE_SEARCHER_PRICES)
    args = parser.parse_args()
    data = add_wine_names(json.loads(args.data.read_text(encoding='utf-8')))
    add_wine_searcher_prices(data, args.wine_searcher_prices)
    embedded_json = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    page = (ROOT / 'page.html').read_text(encoding='utf-8').replace('/* DASHBOARD_STYLES */', (ROOT / 'styles.css').read_text(encoding='utf-8')).replace('/* DASHBOARD_SCRIPT */', (ROOT / 'app.js').read_text(encoding='utf-8')).replace('/* DASHBOARD_DATA */', embedded_json)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding='utf-8')


if __name__ == '__main__':
    main()
