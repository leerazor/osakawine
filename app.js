'use strict';
const dataset = JSON.parse(document.getElementById('wine-data').textContent);
const { meta, wines } = dataset;
const labels = { red:'레드', white:'화이트', sparkling:'스파클링', rose:'로제', orange:'오렌지', dessert:'디저트·주정강화', set:'세트', other:'기타' };
const stockText = { available:'온라인 주문 가능', out:'온라인 품절', member:'상품 상세 회원 전용' };
const allIds = new Map(wines.map(wine => [wine.id, wine]));
const format = new Intl.NumberFormat('ko-KR');
const usd = new Intl.NumberFormat('en-US', {style:'currency', currency:'USD', minimumFractionDigits:0, maximumFractionDigits:2});
const collator = new Intl.Collator('ko');
const fieldNames = ['search', 'country', 'region', 'vintage', 'volume', 'korea', 'comparison', 'stock', 'min', 'max'];
const koreanStores = {dailyshot:['데일리샷', 'dailyshot.co'], gooddeal:['굿딜와인', 'gooddealwine.store'], kihya:['키햐', 'm.kihya.com'], awine:['에이와인', 'awine.kr']};
const $ = id => document.getElementById(id);
const filters = Object.fromEntries(fieldNames.map(name => [name, $(name)]));
const pageSize = 40;
let kind = '';
let visible = pageSize;
let filtered = [];
let activeId = '';
let copiesTimer;

function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[char]));
}
function norm(value) {
  return String(value ?? '').normalize('NFKD').toLowerCase().replace(/\p{Diacritic}/gu, '').replace(/[^\p{L}\p{N}]/gu, '');
}
const spellingAliases = new Map();
const phraseAliases = new Map();
for (const [preferred, ...alternates] of meta.wineNames?.spellings ?? []) {
  for (const spelling of [preferred, ...alternates]) {
    spellingAliases.set(norm(spelling), norm(preferred));
    const phrase = spelling.split(/\s+/).map(norm).join(' ');
    if (phrase.includes(' ')) phraseAliases.set(phrase, norm(preferred));
  }
}
const spellingPattern = spellingAliases.size ? new RegExp([...spellingAliases.keys()].sort((a, b) => b.length - a.length).join('|'), 'gu') : null;
const phrasePattern = phraseAliases.size ? new RegExp('(?<!\\S)(?:' + [...phraseAliases.keys()].sort((a, b) => b.length - a.length).join('|') + ')(?!\\S)', 'gu') : null;
function searchName(value) {
  const key = norm(value);
  return spellingPattern ? key.replace(spellingPattern, spelling => spellingAliases.get(spelling)) : key;
}
function itemLink(url, host) {
  if (!url) return '';
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' && parsed.hostname === host ? escapeHTML(parsed.href) : '';
  } catch { return ''; }
}
function loadSaved() {
  try {
    const values = JSON.parse(localStorage.getItem('takamura-osaka-saved-v1') || '[]');
    return new Set(Array.isArray(values) ? values.filter(id => allIds.has(id)) : []);
  } catch { return new Set(); }
}
const saved = loadSaved();
const searchKeys = new Map(wines.map(wine => [wine.id, [
  wine.koName, ...(wine.koAliases ?? []), wine.jp, wine.enName, wine.en,
  wine.awine?.name, wine.korea?.purchase?.name, wine.korea?.reference?.name,
  wine.producer, wine.country, wine.region, wine.area, wine.vintage, labels[wine.type], wine.id,
  wine.volume ? `${wine.volume} mL` : ''
].filter(Boolean).map(searchName)]));
const asYen = yen => yen == null ? '—' : `¥${format.format(yen)}`;
const asWon = won => won == null ? '—' : `${format.format(Math.round(won))}원`;
const asUsd = amount => amount == null ? '—' : usd.format(amount);
const wineSearcherStatus = wine => wine.wineSearcherUsd === undefined ? '미조회' : '가격 미확인';
const delta = wine => wine.awine?.status === 'exact' && wine.yen != null ? wine.awine.price - Math.round(wine.yen * meta.fx.krwPerYen) : null;
const estimatedPercentage = wine => wine.awine?.estimated && wine.yen != null ? 100 * (wine.awine.price - Math.round(wine.yen * meta.fx.krwPerYen)) / wine.awine.price : null;
const percentage = wine => delta(wine) == null ? null : 100 * delta(wine) / wine.awine.price;
function koreaPurchase(wine) {
  return wine.korea?.purchase ?? (wine.awine?.status === 'exact' && wine.awine.stock === 'available' ? {...wine.awine, store:'awine'} : null);
}
const koreaReference = wine => wine.korea?.reference ?? (wine.awine && !koreaPurchase(wine) ? {...wine.awine, store:'awine'} : null);
const koreaDelta = wine => {
  const price = koreaPurchase(wine)?.price;
  return price && wine.yen != null ? price - Math.round(wine.yen * meta.fx.krwPerYen) : null;
};
const koreaPercentage = wine => koreaDelta(wine) == null ? null : 100 * koreaDelta(wine) / koreaPurchase(wine).price;
const koreaStatus = wine => koreaPurchase(wine) ? 'available' : koreaReference(wine) ? 'reference' : 'unmatched';
const options = (id, values) => values.forEach(([value, title]) => $(id).add(new Option(title, value)));
const unique = values => [...new Set(values.filter(Boolean))];
const numericYear = wine => /^\d{4}$/.test(wine.vintage || '') ? Number(wine.vintage) : null;

function updateSaved() {
  try { localStorage.setItem('takamura-osaka-saved-v1', JSON.stringify([...saved])); } catch { /* Saved selections remain usable until the page closes. */ }
  $('saved-count').textContent = saved.size;
  $('copy-list').disabled = saved.size === 0;
}
function showToast(message) {
  $('toast').textContent = message;
  $('toast').hidden = false;
  clearTimeout(copiesTimer);
  copiesTimer = setTimeout(() => { $('toast').hidden = true; }, 2600);
}
function enquiry(items) {
  const productLines = items.map(wine => `・${wine.jp}（掲載番号 ${wine.id}${wine.volume ? `、${wine.volume}mL` : ''}）\n  ${wine.url}`);
  return ['こんにちは。大阪の江戸堀店に伺う予定です。下記ワインの店頭在庫と税込価格を教えていただけますか。',
    ...productLines,
    '店頭在庫があれば、お取り置きは可能でしょうか。店頭在庫がない場合は、オンライン注文後の店頭受取が可能かも教えていただけると助かります。',
    'よろしくお願いいたします。'].join('\n');
}
async function copyText(value) {
  try { await navigator.clipboard.writeText(value); showToast('일본어 문의 문구를 복사했습니다.'); return; } catch { /* Local files and some browsers restrict clipboard access. */ }
  const area = document.createElement('textarea');
  area.value = value;
  ($('wine-dialog').open ? $('wine-dialog') : document.body).append(area);
  area.select();
  if (document.execCommand('copy')) { area.remove(); showToast('일본어 문의 문구를 복사했습니다.'); }
  else { area.setAttribute('aria-label', '일본어 문의 문구, 선택 후 복사하세요'); area.readOnly = true; area.addEventListener('blur', () => area.remove(), { once:true }); }
}
function stat(number, label) {
  return `<div class="stat"><span>${label}</span><strong>${format.format(number)}</strong></div>`;
}
$('snapshot').textContent = `${meta.checkedDate} 조회 · ¥100 ≈ ${asWon(meta.fx.krwPerYen * 100)} · 온라인 상품가`;
$('stats').innerHTML = [stat(wines.length, '수집한 와인·세트'), stat(wines.filter(wine => koreaStatus(wine) === 'available').length, '한국 구매가 확인'), stat(wines.filter(wine => koreaStatus(wine) === 'reference').length, '한국 참고가만 확인')].join('');
const awineUpdate = meta.awineRecheck ? ` 에이와인 재조회 ${escapeHTML(meta.awineRecheck.date)} · ${format.format(meta.awineRecheck.added)}건 추가.` : '';
const koreaUpdate = meta.korea ? ` 한국 판매처 ${escapeHTML(meta.korea.date)} 대조 · 에이와인 가격이 없던 ${format.format(meta.korea.targets)}개 대상.` : '';
$('basis').innerHTML = `공식몰 전체 표시 ${format.format(meta.catalogTotal ?? 0)}개 · 확인한 고유 상품 ${format.format(meta.listingCount)}개 · 상품 상세 ${format.format(meta.detailsCount)}개${meta.memberOnly ? ` · 상세 회원 전용 ${format.format(meta.memberOnly)}개` : ''}${meta.detailsUnavailable ? ` · 상세 미확인 ${format.format(meta.detailsUnavailable)}개` : ''} · 에이와인 상세 ${format.format(meta.awinePages)}개.${awineUpdate}${koreaUpdate} 환율 ${escapeHTML(meta.fx.date)} 기준. <a href="${escapeHTML(meta.fx.url)}" target="_blank" rel="noopener">환율 출처 ↗</a>`;
if (meta.wineSearcher) {
  const {date, checked, available} = meta.wineSearcher;
  $('wine-searcher-basis').textContent = `와인서쳐 가격은 Gemini가 ${date}에 조회한 전 세계 세전 USD 평균가 참고값입니다. ${format.format(checked)}개 조회 · ${format.format(available)}개 가격 반환. 와인서쳐 원문은 별도 검증하지 않았습니다.`;
}
options('country', unique(wines.map(wine => wine.country)).sort(collator.compare).map(country => [country, country]));
options('region', unique(wines.map(wine => wine.region)).sort(collator.compare).map(region => [region, region]));
options('vintage', unique(wines.map(wine => wine.vintage)).sort((a, b) => b.localeCompare(a)).map(vintage => [vintage, vintage]));
options('volume', unique(wines.map(wine => wine.volume)).filter(ml => ml !== 750).sort((a, b) => a - b).map(ml => [ml, `${format.format(ml)} mL`]));
for (const [value, title] of [['', '전체'], ...Object.entries(labels)]) {
  if (value && !wines.some(wine => wine.type === value)) continue;
  const button = document.createElement('button');
  button.type = 'button'; button.className = 'type'; button.textContent = title; button.dataset.type = value;
  button.setAttribute('aria-pressed', String(value === kind)); $('types').append(button);
}
function setType(value) {
  kind = value;
  $('types').querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.type === value)));
}
function numericOrder(read, direction = 1) {
  return (a, b) => {
    const x = read(a), y = read(b);
    if (x == null || y == null) return Number(x == null) - Number(y == null);
    return direction * (x - y);
  };
}
const sorts = { pct:numericOrder(percentage, -1), estimated:numericOrder(wine => percentage(wine) ?? estimatedPercentage(wine), -1), savings:numericOrder(delta, -1),
  'kr-pct':numericOrder(koreaPercentage, -1), 'kr-savings':numericOrder(koreaDelta, -1),
  'yen-asc':numericOrder(wine => wine.yen), 'yen-desc':numericOrder(wine => wine.yen, -1),
  'ws-asc':numericOrder(wine => wine.wineSearcherUsd), 'ws-desc':numericOrder(wine => wine.wineSearcherUsd, -1),
  'awine-asc':numericOrder(wine => wine.awine?.price), oldest:numericOrder(numericYear) };
function applyFilters() {
  const current = Object.fromEntries(Object.entries(filters).map(([name, el]) => [name, el.value]));
  const query = current.search.split(/\s+/).map(norm).filter(Boolean).join(' ');
  const matchedPhrases = phrasePattern ? query.replace(phrasePattern, phrase => phraseAliases.get(phrase)) : query;
  const terms = matchedPhrases.split(' ').filter(Boolean).map(searchName);
  filtered = wines.filter(wine =>
    (!kind || wine.type === kind) &&
    (!$('saved-only').checked || saved.has(wine.id)) &&
    (!current.country || wine.country === current.country) &&
    (!current.region || wine.region === current.region) &&
    (!current.vintage || (current.vintage === 'old' ? numericYear(wine) != null && numericYear(wine) < 2010 : wine.vintage === current.vintage)) &&
    (!current.volume || (current.volume === 'large' ? wine.volume >= 1500 : wine.volume === Number(current.volume))) &&
    (!current.korea || koreaStatus(wine) === current.korea) &&
    (!current.comparison || (wine.awine?.status || 'unmatched') === current.comparison) &&
    (!current.stock || (wine.onlineStock || 'unknown') === current.stock) &&
    (!current.min || (wine.yen != null && wine.yen >= Number(current.min))) &&
    (!current.max || (wine.yen != null && wine.yen <= Number(current.max))) &&
    terms.every(term => searchKeys.get(wine.id).some(name => name.includes(term)))
  );
  const sort = sorts[$('sort').value];
  if (sort) filtered.sort(sort);
  visible = pageSize;
  render();
}
function originalNames(wine) {
  const japanese = `<p lang="ja">${escapeHTML(wine.jp)}</p>`;
  const english = wine.enName || wine.en;
  return `<div class="original-names">${japanese}${english ? `<p lang="en">${escapeHTML(english)}</p>` : ''}</div>`;
}
function card(wine) {
  const purchase = koreaPurchase(wine);
  const korean = purchase ?? koreaReference(wine);
  const main = wine.koName || wine.en || wine.jp;
  const details = [labels[wine.type], wine.pack ? `${wine.pack}병` : '', wine.country, wine.region, wine.vintage, wine.volume ? `${wine.volume}mL` : '', ['out','member'].includes(wine.onlineStock) ? stockText[wine.onlineStock] : ''].filter(Boolean);
  const won = wine.yen == null ? '—' : asWon(wine.yen * meta.fx.krwPerYen);
  const pct = koreaPercentage(wine);
  const store = koreanStores[korean?.store]?.[0];
  const reference = korean?.stock === 'out' ? '품절 참고가'
    : korean?.stock === 'request' ? '재고 미확정 참고가'
    : korean?.vintage && wine.vintage && korean.vintage !== wine.vintage ? `${korean.vintage} 참고가`
    : korean?.notes?.includes('빈티지 미표기') ? '빈티지 미표기 참고가' : '참고가';
  const hint = pct != null ? `<small class="${pct >= 0 ? 'saving' : 'premium'}">${Math.abs(pct).toFixed(1)}% ${pct >= 0 ? '저렴' : '높음'}</small>`
    : korean ? `<small>${escapeHTML(reference)}</small>` : '';
  return `<article class="wine"><div><h3>${escapeHTML(main)}</h3>${originalNames(wine)}<p class="meta">${details.map(value => `<span>${escapeHTML(value)}</span>`).join('')}</p></div>
    <dl class="prices"><div><dt>타카무라 온라인가</dt><dd>${asYen(wine.yen)}<small>${won}</small></dd></div>
    <div><dt>${purchase ? '한국 구매가' : '한국 참고가'}${store ? ` · ${escapeHTML(store)}` : ''}</dt><dd>${asWon(korean?.price)}${hint}</dd></div>
    <div><dt>와인서쳐 가격</dt><dd>${asUsd(wine.wineSearcherUsd)}<small>${wine.wineSearcherUsd == null ? wineSearcherStatus(wine) : 'Gemini 조회 · 세전'}</small></dd></div></dl>
    <div class="wine-actions"><button class="secondary" type="button" data-detail="${wine.id}">상세</button><button class="secondary" type="button" data-save="${wine.id}" aria-pressed="${saved.has(wine.id)}">${saved.has(wine.id) ? '찜 해제' : '찜'}</button></div></article>`;
}
function render() {
  const shown = Math.min(visible, filtered.length);
  $('count').textContent = `${format.format(filtered.length)}건${shown < filtered.length ? ` 중 ${format.format(shown)}건 표시` : ''}`;
  $('results').innerHTML = filtered.slice(0, visible).map(card).join('');
  $('more').hidden = shown >= filtered.length;
  $('empty').hidden = filtered.length > 0;
}
function koreanDetails(wine) {
  const purchase = koreaPurchase(wine);
  const offer = purchase ?? koreaReference(wine);
  if (!offer || offer.store === 'awine') return '';
  const diff = koreaDelta(wine);
  const saving = diff == null ? '' : `<p>한국 구매가 대비 ${asWon(Math.abs(diff))} ${diff >= 0 ? '저렴' : '높음'}</p>`;
  if (offer.components) {
    const items = offer.components.map(part => {
      const [seller, host] = koreanStores[part.store];
      const url = itemLink(part.url, host);
      const name = `${escapeHTML(part.name)} · ${escapeHTML(seller)}`;
      return `<li>${url ? `<a target="_blank" rel="noopener" href="${url}">${name} ↗</a>` : name} · ${asWon(part.price)} × ${part.count}병</li>`;
    });
    return `<h3>한국 구매가</h3><p>${asWon(offer.price)} · 동일 구성품 합계 · ${escapeHTML(offer.date)}</p><ul>${items.join('')}</ul>${saving}`;
  }
  const [seller, host] = koreanStores[offer.store] ?? [];
  const url = itemLink(offer.url, host);
  const alternative = purchase ? koreaReference(wine) : null;
  const [alternativeSeller, alternativeHost] = koreanStores[alternative?.store] ?? [];
  const alternativeURL = itemLink(alternative?.url, alternativeHost);
  const conditional = alternative?.stock === 'request' ? `<p>재고 미확정 참고가 · ${asWon(alternative.price)}${alternativeURL ? ` · <a target="_blank" rel="noopener" href="${alternativeURL}">${escapeHTML(alternativeSeller)} ↗</a>` : ''}</p>` : '';
  const conditions = [offer.vintage || '빈티지 미표기', offer.volume ? `${offer.volume}mL` : '용량 미표기', offer.method, offer.date]
    .filter(Boolean).map(escapeHTML).join(' · ');
  return `<h3>${purchase ? '한국 구매가' : '한국 참고가'}</h3><p>${asWon(offer.price)} · ${escapeHTML(seller)} · ${conditions}</p>
    ${saving}${offer.notes?.length ? `<p>${offer.notes.map(escapeHTML).join(' · ')}</p>` : ''}
    ${url ? `<p><a target="_blank" rel="noopener" href="${url}">${escapeHTML(seller)} 상품 ↗</a></p>` : ''}${conditional}`;
}
function openDetails(wine) {
  activeId = wine.id;
  const product = itemLink(wine.url, 'takamuraplus.jp');
  const awine = itemLink(wine.awine?.url, 'awine.kr');
  const vivino = itemLink(wine.vivino, 'www.vivino.com');
  const match = wine.awine;
  let matchInfo = '<p>대조할 가격을 확인하지 못했습니다.</p>';
  if (match?.components) {
    const parts = match.components.map(part => {
      const link = itemLink(part.url, 'awine.kr');
      return `<li>${link ? `<a target="_blank" rel="noopener" href="${link}">${escapeHTML(part.name)} ↗</a>` : escapeHTML(part.name)} · ${asWon(part.price)} × ${part.count}병</li>`;
    });
    matchInfo = `<p>구성품 합계 ${asWon(match.price)} · ${escapeHTML(match.date)} 조회</p><ul>${parts.join('')}</ul>`;
  } else if (match) {
    matchInfo = `<p>${asWon(match.price)} · ${escapeHTML(match.vintage || '빈티지 미표기')} · ${match.volume ? `${match.volume}mL` : '용량 미표기'} · ${escapeHTML(match.date)} 조회</p>`;
  }
  const heading = wine.koName || wine.en || wine.jp;
  $('detail-content').innerHTML = `<h2 id="detail-title">${escapeHTML(heading)}</h2>${originalNames(wine)}
    ${wine.enNameSupplemented ? '<p class="muted">영문명은 일본어 상품명을 바탕으로 보완했습니다.</p>' : ''}
    <p class="muted">${[wine.id, wine.producer, wine.area, wine.vintage, wine.volume ? `${wine.volume}mL` : ''].filter(Boolean).map(escapeHTML).join(' · ')}</p>
    <h3>타카무라 플러스</h3><p>${asYen(wine.yen)} · ${asWon(wine.yen == null ? null : wine.yen * meta.fx.krwPerYen)} · ${stockText[wine.onlineStock] || '온라인 재고 미확인'}</p>
    <p>에도보리 매장 재고와 판매가 확인 필요${product ? ` · <a target="_blank" rel="noopener" href="${product}">공식몰 상품 ↗</a>` : ''}</p>
    ${koreanDetails(wine)}
    ${!koreaPurchase(wine) && !koreaReference(wine) ? '<h3>한국 가격</h3><p>조회한 판매처에서 비교할 상품 가격을 확인하지 못했습니다.</p>' : ''}
    <h3>와인서쳐 가격</h3><p>${wine.wineSearcherUsd == null ? wineSearcherStatus(wine) : `${asUsd(wine.wineSearcherUsd)} · 전 세계 세전 평균가 · Gemini 조회 ${escapeHTML(meta.wineSearcher.date)} · 원문 미검증`}</p>
    <h3>에이와인</h3>${matchInfo}${match?.notes.length ? `<p>참고가 · ${match.notes.map(escapeHTML).join(' · ')}</p>` : ''}
    ${match?.status === 'exact' && delta(wine) != null ? `<p>에이와인 대비 ${asWon(Math.abs(delta(wine)))} ${delta(wine) >= 0 ? '저렴' : '높음'}</p>` : ''}
    ${awine ? `<p><a target="_blank" rel="noopener" href="${awine}">에이와인 상품 ↗</a></p>` : ''}
    ${vivino ? `<p><a target="_blank" rel="noopener" href="${vivino}">Vivino 와인 정보 ↗</a></p>` : ''}
    <h3>매장 문의 문구</h3><textarea readonly lang="ja" aria-label="일본어 매장 문의 문구">${escapeHTML(enquiry([wine]))}</textarea>`;
  $('wine-dialog').showModal();
}
$('types').addEventListener('click', event => {
  const button = event.target.closest('[data-type]');
  if (button) { setType(button.dataset.type); applyFilters(); }
});
for (const control of [...Object.values(filters), $('sort'), $('saved-only')]) control.addEventListener('input', applyFilters);
$('reset').addEventListener('click', () => {
  for (const [name, el] of Object.entries(filters)) el.value = name === 'volume' ? '750' : '';
  setType(''); $('saved-only').checked = false; applyFilters();
});
$('results').addEventListener('click', event => {
  const detail = event.target.closest('[data-detail]');
  const saveButton = event.target.closest('[data-save]');
  if (detail) openDetails(allIds.get(detail.dataset.detail));
  if (saveButton) {
    const id = saveButton.dataset.save;
    if (saved.has(id)) saved.delete(id); else saved.add(id);
    updateSaved();
    if ($('saved-only').checked) applyFilters();
    else { saveButton.textContent = saved.has(id) ? '찜 해제' : '찜'; saveButton.setAttribute('aria-pressed', String(saved.has(id))); }
  }
});
$('close-dialog').addEventListener('click', () => $('wine-dialog').close());
$('copy-wine').addEventListener('click', () => copyText(enquiry([allIds.get(activeId)])));
$('copy-list').addEventListener('click', () => copyText(enquiry([...saved].map(id => allIds.get(id)))));
$('more').addEventListener('click', () => { visible += pageSize; render(); });
updateSaved();
applyFilters();
