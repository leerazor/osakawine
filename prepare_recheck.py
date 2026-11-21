"""Select additional AWINE detail pages for wines that had no original candidate."""
from argparse import ArgumentParser
from collections import defaultdict
from math import log
from pathlib import Path
from urllib.parse import unquote, urlsplit
import re

from collect import read_json, save
from compare import GENERIC, candidate_index, candidate_urls, identity_words, slug_name

CANDIDATE_NOISE = {'tenuta', 'dell', 'delle', 'della', 'di', 'de', 'le', 'la', 'annee',
                   'jahrgang', 'millesime', 'co', 'company'}
COMMON_WORDS = GENERIC | {'millesime', 'special', 'france', 'italia', 'italy', 'vin', 'vintage'}
COLORS = {'rose', 'blanc', 'rouge'}
YEAR = re.compile(r'(?<!\d)(?:18|19|20)\d{2}(?!\d)')


def search_words(title):
    return frozenset(word for word in identity_words(title)
                     if word not in CANDIDATE_NOISE and len(word) > 1 and not word.isdecimal())


def search_index(urls):
    indexed = []
    postings = defaultdict(set)
    for url in urls:
        words = search_words(slug_name(url))
        if not words:
            continue
        slug = unquote(urlsplit(url).path.rstrip('/').rsplit('/', 1)[-1])
        position = len(indexed)
        indexed.append((url, words, set(YEAR.findall(slug))))
        for word in words:
            postings[word].add(position)
    weights = {word: log(1 + len(indexed) / (1 + len(matches))) for word, matches in postings.items()}
    return indexed, postings, weights


def shortlist(row, indexed, postings, weights):
    words = search_words(row['en'])
    distinct = words - COMMON_WORDS
    rare = sorted(distinct & postings.keys(), key=lambda word: (len(postings[word]), word))[:6]
    if not rare:
        return []

    def weight(tokens):
        return sum(weights.get(word, 4.0) for word in tokens)

    row_weight = weight(words)
    scores = []
    for pos in set.union(*(postings[word] for word in rare)):
        url, candidate, years = indexed[pos]
        shared = words & candidate
        if len(shared) < min(2, len(words)) or not shared & distinct:
            continue
        shared_weight = weight(shared)
        coverage = shared_weight / row_weight
        purity = shared_weight / weight(candidate)
        if coverage < 0.53 or purity < 0.34:
            continue
        exact_year = row['vintage'] in years
        color_conflict = bool(COLORS & (candidate - words)) and bool(COLORS & (words - candidate))
        score = 0.70 * coverage + 0.30 * purity + 0.23 * exact_year - 0.36 * color_conflict
        scores.append((score, exact_year, url))
    return [url for _, _, url in sorted(scores, reverse=True)[:5]]


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--additional-plan', type=Path)
    args = parser.parse_args()
    urls = read_json(args.cache / 'awine-urls.json', [])
    snapshot = read_json(args.snapshot, {})
    rows = snapshot['wines']
    old_names, old_index = candidate_index(urls)
    expanded_index = search_index(urls)
    candidate_plan = {}
    for row in rows:
        if row.get('awine') or row['type'] == 'set' or candidate_urls(row, old_names, old_index):
            continue
        selected = shortlist(row, *expanded_index)
        if selected:
            candidate_plan[row['id']] = selected
    target = list(candidate_plan)
    if args.additional_plan:
        for sku, selected in read_json(args.additional_plan, {})['candidateUrls'].items():
            candidate_plan.setdefault(sku, selected)
    urls = list(dict.fromkeys(url for selected in candidate_plan.values() for url in selected))
    args.output.mkdir(parents=True, exist_ok=True)
    known = {**read_json(args.cache / 'awine-details.json', {}),
             **read_json(args.output / 'awine-details.json', {})}
    save(args.output / 'plan.json', {'target': target, 'candidates': candidate_plan,
                                    'takamuraCheckedDate': snapshot['meta']['checkedDate']})
    save(args.output / 'awine-candidates.json', urls)
    save(args.output / 'awine-details.json', {url: known[url] for url in urls if url in known})
    print(f'{len(target)} new target rows, {len(urls)} detail pages in the plan')


if __name__ == '__main__':
    main()
