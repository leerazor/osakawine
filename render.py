"""Package the dashboard as one HTML file that works without a server."""
from pathlib import Path
import argparse
import json

from wine_names import add_wine_names

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = add_wine_names(json.loads(args.data.read_text(encoding='utf-8')))
    embedded_json = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    page = (ROOT / 'page.html').read_text(encoding='utf-8').replace('/* DASHBOARD_STYLES */', (ROOT / 'styles.css').read_text(encoding='utf-8')).replace('/* DASHBOARD_SCRIPT */', (ROOT / 'app.js').read_text(encoding='utf-8')).replace('/* DASHBOARD_DATA */', embedded_json)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding='utf-8')


if __name__ == '__main__':
    main()
