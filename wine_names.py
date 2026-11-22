"""Add searchable Korean and Latin-script display names to Takamura records."""
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KANA = r'[ァ-ヺーヽヾ]+'
HAN = re.compile(r'[㐀-鿿々]')
HANGUL = re.compile(r'[가-힣]')
YEAR = re.compile(r'(?<!\d)(?:19|20)\d{2}(?!\d)')
SIZE = re.compile(r'\b\d+(?:\.\d+)?\s*(?:mL|L)\b', re.I)
TAGS = re.compile(r'\s*[\[【](?:送料無料|限定特価|正規品|正規|数量限定|特価|[A-Z])[\]】]')
STYLE_SUFFIX = re.compile(r'\(\s*(?:赤\s*ワイン|白\s*ワイン|ロゼ\s*ワイン|泡\s*[白赤ロ]|オレンジ|果実酒|(?:赤|白)\s*甘口|追加|ワイン\s*\()', re.I)
PROMOTION = re.compile(r'送料無料|ベストセラー|限定特価|数量限定|蔵出し|旨安(?:大賞|賞)|サクラ\s*アワード\s*ダブル\s*ゴールド|'
                       r'リピーター続出[^!！]*!|\d+点生産者[^!！]*!|\d+周年記念(?:ボトル)?|'
                       r'お一人様\s*\d+\s*(?:本|セット)限り|(?<![ァ-ヿ])(?:正規輸入品|正規品|正規|並行輸入品|並行)(?![ァ-ヿ])')
BASE_YEAR = re.compile(r'[（(]\s*※?ベース\s*((?:19|20)\d{2})\s*年?\s*(?:ヴィンテージ)?\s*[）)]')
KANA_ROWS = (
    ('アイウエオ', '아 이 우 에 오', 'a i u e o'),
    ('カキクケコ', '카 키 쿠 케 코', 'ka ki ku ke ko'),
    ('ガギグゲゴ', '가 기 구 게 고', 'ga gi gu ge go'),
    ('サシスセソ', '사 시 스 세 소', 'sa shi su se so'),
    ('ザジズゼゾ', '자 지 즈 제 조', 'za ji zu ze zo'),
    ('タチツテト', '타 치 쓰 테 토', 'ta chi tsu te to'),
    ('ダヂヅデド', '다 지 즈 데 도', 'da ji zu de do'),
    ('ナニヌネノ', '나 니 누 네 노', 'na ni nu ne no'),
    ('ハヒフヘホ', '하 히 후 헤 호', 'ha hi fu he ho'),
    ('バビブベボ', '바 비 부 베 보', 'ba bi bu be bo'),
    ('パピプペポ', '파 피 푸 페 포', 'pa pi pu pe po'),
    ('マミムメモ', '마 미 무 메 모', 'ma mi mu me mo'),
    ('ヤユヨ', '야 유 요', 'ya yu yo'),
    ('ラリルレロ', '라 리 루 레 로', 'ra ri ru re ro'),
    ('ワヰヱヲ', '와 이 에 오', 'wa i e o'),
    ('ァィゥェォャュョヮヴ', '아 이 우 에 오 야 유 요 와 브', 'a i u e o ya yu yo wa vu'),
)
KANA_PAIRS = {
    'イェ': ('예', 'ye'), 'ウィ': ('위', 'wi'), 'ウェ': ('웨', 'we'), 'ウォ': ('워', 'wo'),
    'クァ': ('콰', 'kwa'), 'クィ': ('퀴', 'kwi'), 'クェ': ('퀘', 'kwe'), 'クォ': ('쿼', 'kwo'),
    'グァ': ('과', 'gwa'), 'ツァ': ('차', 'tsa'), 'ツィ': ('치', 'tsi'), 'ツェ': ('체', 'tse'), 'ツォ': ('초', 'tso'),
    'シェ': ('셰', 'she'), 'ジェ': ('제', 'je'), 'チェ': ('체', 'che'),
    'ティ': ('티', 'ti'), 'ディ': ('디', 'di'), 'トゥ': ('투', 'tu'), 'ドゥ': ('두', 'du'),
    'テュ': ('튀', 'tyu'), 'デュ': ('뒤', 'dyu'), 'スィ': ('시', 'si'), 'ズィ': ('지', 'zi'),
    'ファ': ('파', 'fa'), 'フィ': ('피', 'fi'), 'フェ': ('페', 'fe'), 'フォ': ('포', 'fo'),
    'フュ': ('퓨', 'fyu'), 'ヴァ': ('바', 'va'), 'ヴィ': ('비', 'vi'), 'ヴェ': ('베', 've'), 'ヴォ': ('보', 'vo'),
    'ヴュ': ('뷰', 'vyu'), 'シィ': ('시', 'shi'), 'フャ': ('퍄', 'fya'),
}
for kana, starts, latin in (
    ('キ', '캬 큐 쿄', 'ky'), ('ギ', '갸 규 교', 'gy'), ('シ', '샤 슈 쇼', 'sh'),
    ('ジ', '쟈 쥬 죠', 'j'), ('チ', '챠 츄 쵸', 'ch'), ('ニ', '냐 뉴 뇨', 'ny'),
    ('ヒ', '햐 휴 효', 'hy'), ('ビ', '뱌 뷰 뵤', 'by'), ('ピ', '퍄 퓨 표', 'py'),
    ('ミ', '먀 뮤 묘', 'my'), ('リ', '랴 류 료', 'ry'),
):
    for tail, syllable, vowel in zip('ャュョ', starts.split(), 'auo'):
        KANA_PAIRS[kana + tail] = (syllable, latin + vowel)
KANA_MAP = {
    kana: (hangul, latin)
    for kana_row, ko_row, latin_row in KANA_ROWS
    for kana, hangul, latin in zip(kana_row, ko_row.split(), latin_row.split())
}
KANA_MAP.update(KANA_PAIRS)

SPELLINGS = (
    ('샤또', '샤토'), ('무똥', '무통'), ('로칠드', '로쉴드', '로트실트', '롯쉴드'),
    ('오브리옹', '오 브리옹', '오브리용', '오브리온'), ('라투르', '라뚜르'),
    ('퐁테 카네', '뽕떼 까네', '퐁테 까네', '폰테 카네'),
    ('피숑', '피쏭'), ('꽁떼스', '콩테스', '꽁테스'), ('라랑드', '랄랑드'),
    ('꼬스 데스투르넬', '코스 데스투르넬', '코스 데스투르넬르', '꼬스 데스뚜르넬'),
    ('린치 바쥬', '린치 바주', '랑슈 바쥬'), ('라스까스', '라스 카즈', '라스 카스'),
    ('칼롱 세귀르', '칼롱 세규르', '깔롱 세귀르', '칼롱 세기르'),
    ('끌레르 밀롱', '끄레르 밀롱', '클레르 밀롱'), ('팔머', '팔메', '팔메르'),
    ('쥬브레', '쥐브레', '쥬브레이', '주브레'), ('샹베르탱', '샹베르땡', '샹베르텡'),
    ('본 로마네', '보느 로마네', '보느로마네', '본 로마니'), ('뉘 생 조르주', '뉘 쌩 조르쥐', '뉘 쌩 조르주'),
    ('샹볼 뮈지니', '샹볼 뮈지니에', '샹볼 뮤지니'), ('퓔리니', '뿔리니', '풀리니', '퓔리니에'),
    ('몽라쉐', '몽라셰', '몽라체', '몽라쎄'), ('샤사뉴', '샤샤뉴', '샤싸뉴'), ('뫼르소', '뫼르쏘', '므르소'),
    ('꼬르통', '코르통', '꼬르똥'), ('부르고뉴', '부르고뉘', '버건디'), ('그랑 크뤼', '그랑 크루'),
    ('프리미에 크뤼', '프리미에 크루', '프르미에 크뤼', '프리미어 크뤼'),
    ('끌로', '클로'), ('도멘', '도메인'), ('샤르도네', '샤도네이', '샤도네', '샤르도네이'),
    ('카베르네', '까베르네', '카버네', '까버네'), ('소비뇽', '쇼비뇽'), ('메를로', '멜롯', '메를롯', '메를로트'),
    ('피노 누아', '피노 누아르'), ('슈냉', '쉐냉'), ('뮈스카데', '뮤스카데'), ('뫼니에', '뮈니에', '뮤니에'),
    ('샹파뉴', '샴페인', '상파뉴'), ('뀌베', '큐베', '퀴베'), ('브뤼', '브뤼트', '브룻'),
    ('비에이 비뉴', '비에유 비뉴', '비에유 빈뉴', '비에이 빈뉴'),
    ('노즈', '노제'), ('루즈', '루주'), ('쁘띠', '프티', '프띠', '쁘티'), ('꼬뜨', '코트', '꼬트', '코뜨'),
    ('볼랭저', '볼랭져', '볼링저', '볼랑제'), ('라에르뜨', '라에르트', '라헤르트', '라에르떼'),
    ('로드레', '로데레르', '로더러', '로드레르'), ('돔 페리뇽', '동 페리뇽', '돈 페리뇽'),
    ('크룩', '크루그', '크뤽'), ('살롱', '살론'), ('셀로스', '셀로쓰'), ('베레슈', '베레쉬'),
    ('들라모뜨', '델라모뜨', '델라모트', '들라모트'), ('루이나', '뤼나르', '루이나르'),
    ('폴 로저', '뽈 로제', '폴 로제'), ('로랑 페리에', '로랑 페리어'),
    ('끼안티', '키안티', '치안티'), ('바롤로', '바로로'), ('사시까이아', '사시카이아'),
    ('오퍼스 원', '오푸스 원', '오파스 원'), ('오버추어', '오버츄어'), ('케이머스', '케이무스'),
    ('코슈 뒤리', '코쉬 뒤리', '코슈 듀리'), ('푸리에', '후리에', '푸리예'),
    ('필립 파칼레', '필리프 파칼레', '필립 빠칼레'), ('프레데릭 코사르', '프레데릭 코사르트'),
    ('아르망 루소', '아르망 루쏘'), ('아르누 라쇼', '아르노 라쇼', '아흐누 라쇼'),
    ('르플레브', '르플레브르'), ('메오 까뮈제', '메오 카뮈제', '메오 카뮤제'),
    ('프리에르 로크', '프리외레 로크', '프리외레 록', '프리외레 호끄', '프리에르 록'),
    ('라브노', '라브노우'), ('르루아', '르로이', '르루와'), ('조르주 루미에', '조르쥬 루미에'),
    ('리아르', '리야르'), ('부샤르', '부샤'), ('조셉', '조제프'),
    ('쥘리앵', '줄리앙', '쥴리앙'), ('콜랭', '콜린', '꼴랭'), ('뱅상', '방상', '뱅쌍'),
    ('벨 에포크', '벨 에뽀끄', '벨 에포끄'), ('논빈티지', '논빈'),
    ('알디', '아르디'), ('매그넘', '마그넘'),
)


def plain(value):
    value = unicodedata.normalize('NFKC', str(value or ''))
    value = re.sub(r'(?<=[ァ-ヺ])[ \t]+(?=[\u3099\u309a])', '', value)
    return unicodedata.normalize('NFC', value)


def compact(value):
    value = unicodedata.normalize('NFKD', str(value or '').casefold())
    return ''.join(char for char in value if char.isalnum())


def clean_spaces(value):
    return re.sub(r'\s+', ' ', value).strip(' .・·―/–')


def kana_fold(value):
    return ''.join(chr(ord(c) + 96) if 'ぁ' <= c <= 'ゖ' else c for c in value)


def load_terms():
    terms = {}
    for line in (ROOT / 'wine_name_terms.tsv').read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#'):
            source, korean = line.split('\t')
            terms[kana_fold(plain(source))] = korean
    return terms


TERMS = load_terms()
TERM_RE = re.compile('|'.join(r'\s*'.join(map(re.escape, key.split())) for key in sorted(TERMS, key=len, reverse=True)))
COMPACT_TERMS = {''.join(key.split()): value for key, value in TERMS.items()}


def add_coda(value, consonant):
    if value and '가' <= value[-1] <= '힣' and (ord(value[-1]) - ord('가')) % 28 == 0:
        return value[:-1] + chr(ord(value[-1]) + consonant)
    return value


def roman_or_hangul(run, latin=False, foreign=False):
    result = ''
    position = 0
    doubled = False
    while position < len(run):
        mark = run[position]
        if mark == 'ン':
            result = result + 'n' if latin else add_coda(result, 4) or '은'
        elif mark == 'ッ':
            doubled = latin
        elif mark not in 'ーヽヾ':
            unit = run[position:position + 2]
            if unit in KANA_PAIRS:
                position += 1
            else:
                unit = mark
            transliterated = KANA_MAP.get(unit, ('', ''))[int(latin)]
            if foreign and not latin and position == len(run) - 1:
                transliterated = {'ル': '르', 'ク': '크', 'ト': '트', 'ド': '드', 'フ': '프',
                                  'ム': '므', 'プ': '프', 'グ': '그', 'ブ': '브'}.get(unit, transliterated)
            if doubled and transliterated:
                result += 't' if transliterated.startswith('ch') else transliterated[0]
            result += transliterated
            doubled = False
        position += 1
    return result


def koreanize(value, foreign=False):
    value = kana_fold(plain(value)).replace('・', ' ').replace('･', ' ')
    value = re.sub(r'(?<=[ァ-ヺ])[―－−](?=[ァ-ヺ])', 'ー', value)
    value = TERM_RE.sub(lambda match: ' ' + COMPACT_TERMS[''.join(match[0].split())] + ' ', value)
    value = re.sub(r'(?<![ァ-ヺ])ド(?![ァ-ヺ])', ' 드 ', value)
    value = re.sub(KANA, lambda match: roman_or_hangul(match[0], foreign=foreign), value)
    return clean_spaces(value)


def remove_tags(title):
    title = TAGS.sub(' ', plain(title))
    title = BASE_YEAR.sub(' ', title)
    title = STYLE_SUFFIX.split(title, maxsplit=1)[0]
    title = re.split(r'※|\(\s*\d+本(?:同梱可|限り)|\(\s*(?:追加|同梱|お一人様)', title, maxsplit=1)[0]
    title = re.sub(r'^\s*(?:\[[^\]]*\]\s*)+(?=\D)', '', title)
    title = re.sub(r'【(?:WS|JS|\d+%OFF|限定ポイント)[^】]*】', ' ', title)
    title = PROMOTION.sub(' ', title)
    title = re.sub(r'\[\s*((?:19|20)\d{2})\s*\]', r' \1 ', title)
    title = re.sub(r'(?<=[ァ-ヺ])(?=NV(?![A-Za-z]))|(?<=NV)(?=[ァ-ヺ])', ' ', title, flags=re.I)
    title = re.sub(r'(?:計\s*)?(\d+)\s*本\s*セット', r' \1병 세트', title)
    return clean_spaces(title.strip(' ◎☆★!！'))


def offer_base(name, wine):
    title = re.sub(r'^\s*(?:\[[^]]+\]\s*)+', '', plain(name))
    title = re.sub(r'\[\s*((?:19|20)\d{2})\s*\]', r' \1 ', title)
    title = re.sub(r'\s*(?:\([^()]*\b(?:750\s*mL|배송|예약|픽업)[^()]*\))\s*', ' ', title, flags=re.I)
    return add_vintage(clean_spaces(YEAR.sub(' ', title)), wine.get('vintage'))


def add_vintage(title, vintage):
    if vintage and (vintage not in YEAR.findall(title) if vintage != 'NV' else not re.search(r'\bNV\b|논\s*빈티지', title, re.I)):
        return clean_spaces(f'{title} {vintage}')
    return title


def latin_identity(value):
    value = YEAR.sub(' ', plain(value).lower())
    value = SIZE.sub(' ', value)
    value = re.sub(r'\bn[.\s-]*v\b|\b(?:magnum|jeroboam|double magnum)\b', ' ', value)
    value = unicodedata.normalize('NFKD', value)
    value = ''.join(c for c in value if not unicodedata.combining(c))
    words = set(re.findall(r'[a-z]+[a-z0-9]*', value))
    return frozenset(words - {'de', 'du', 'des', 'd', 'l', 'la', 'le', 'les', 'and', 'et', 'of', 'the'})


def same_wine_offers(wine):
    korean = wine.get('korea', {})
    offers = [korean.get('purchase'), wine.get('awine'), korean.get('reference')]
    identity = latin_identity(wine.get('en'))
    for offer in offers:
        if not offer or offer.get('components') or not HANGUL.search(offer.get('name', '')):
            continue
        # Price matches sometimes use a neighbouring vintage. Check the
        # cuvée again before reusing its Korean title or removing its year.
        if identity and identity == latin_identity(offer.get('en')):
            yield offer


def readable_sources(wine):
    original = wine.get('en', '').strip()
    if re.search(r'[A-Za-zÀ-ÖØ-öø-ÿ]{2,}', original) and not re.fullmatch(r'n/?a|nv|none|unknown', original, re.I):
        title = original.split('※', 1)[0].replace('ー', '-').replace('・', '.')
        title = add_vintage(clean_spaces(re.sub(r'\bMeulsaut\b', 'Meursault', title)), wine.get('vintage'))
        if wine['type'] == 'set' and wine.get('pack') and not re.search(r'\b(?:set|bottles)\b', title, re.I):
            title += f' · set of {wine["pack"]} bottles'
        return title, False
    title = remove_tags(wine.get('jp'))
    latin = re.sub(KANA, lambda match: roman_or_hangul(match[0], latin=True).capitalize(), kana_fold(title))
    latin = re.sub(r'(\d+)\s*병\s*Setto', r'\1-bottle set', latin)
    latin = HAN.sub('', latin)
    return add_vintage(clean_spaces(latin) or f'Product {wine["id"]}', wine.get('vintage')), True


def load_overrides():
    result = {}
    for line in (ROOT / 'wine_names_overrides.tsv').read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#'):
            sku, korean, english = line.split('\t')
            result[sku.zfill(12)] = (korean, english)
    return result


def add_wine_names(data):
    overrides = load_overrides()
    known = defaultdict(dict)
    for wine in data['wines']:
        if wine.get('type') == 'set':
            continue
        identity = (latin_identity(wine.get('en')), wine.get('type'))
        for offer in same_wine_offers(wine):
            known[identity][offer['name']] = None

    for wine in data['wines']:
        override, english = overrides.get(wine['id'], ('', ''))
        original = remove_tags(wine.get('jp'))
        foreign = wine.get('country') != '일본'
        japanese_korean = add_vintage(koreanize(original, foreign), wine.get('vintage'))
        producer_korean = koreanize(wine.get('producer'), foreign)
        # The Japanese catalog has the fuller product title for sets,
        # bottle sizes, vines, and other variants. Prefer it as the base.
        title = override or japanese_korean
        offers = list(same_wine_offers(wine)) if wine['type'] != 'set' else []
        offer_names = [offer_base(offer['name'], wine) for offer in offers]
        if not override and offers and wine.get('volume') in (None, 750) and not re.search(r'\d+\s*(?:本|병)|セット|木箱|マグナム|ジェロボアム', original):
            exact = next((offer for offer in offers if offer.get('vintage') == wine.get('vintage')), None)
            if exact is not None:
                title = offer_base(exact['name'], wine)
        if not HANGUL.search(title):
            title = clean_spaces(f'{producer_korean} 와인 {title}')
        if HAN.search(title) or re.search(KANA, title):
            title = clean_spaces(HAN.sub(' ', title))
            title = re.sub(KANA, lambda match: roman_or_hangul(match[0], foreign=foreign), title)
        title = re.sub(r'[\u3099\u309a]', '', title)
        wine['koName'] = clean_spaces(title)
        original_en, alternate = readable_sources(wine)
        wine['enName'] = original_en if not alternate else english or original_en
        if alternate:
            wine['enNameSupplemented'] = True
        identity = (latin_identity(wine.get('en')), wine.get('type'))
        aliases = [japanese_korean, producer_korean, *offer_names]
        if wine.get('vintage') == 'NV':
            aliases.append('논빈티지')
        if 'bollinger' in wine['enName'].lower() and re.search(r'\bR\s*\.?\s*D\b', wine['enName'], re.I):
            aliases.append('볼랭저 알디')
        if len(identity[0]) >= 3 and wine['type'] != 'set':
            aliases.extend(offer_base(name, wine) for name in known.get(identity, {}))
        seen = {compact(wine['koName']): None}
        wine['koAliases'] = []
        for name in aliases:
            key = compact(name)
            if key and key not in seen and HANGUL.search(name):
                seen[key] = None
                wine['koAliases'].append(name)
    data['meta']['wineNames'] = {'korean': len(data['wines']),
                                 'englishSupplemented': sum(wine.get('enNameSupplemented', False) for wine in data['wines']),
                                 'spellings': SPELLINGS}
    return data
