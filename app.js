'use strict';
const dataset = JSON.parse(document.getElementById('wine-data').textContent);
const { meta, wines } = dataset;
const labels = { red:'레드', white:'화이트', sparkling:'스파클링', rose:'로제', orange:'오렌지', dessert:'디저트·주정강화', set:'세트', other:'기타' };
const stockText = { available:'온라인 주문 가능', out:'온라인 품절', member:'상품 상세 회원 전용' };
const allIds = new Map(wines.map(wine => [wine.id, wine]));
const format = new Intl.NumberFormat('ko-KR');
const collator = new Intl.Collator('ko');
const fieldNames = ['search', 'country', 'region', 'vintage', 'volume', 'comparison', 'stock', 'min', 'max'];
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
const searchKeys = new Map(wines.map(wine => [wine.id, norm([
  wine.jp, wine.en, wine.awine?.name, wine.producer, wine.country, wine.region, wine.area, wine.vintage, labels[wine.type], wine.id
].filter(Boolean).join(' '))]));
const asYen = yen => yen == null ? '—' : `¥${format.format(yen)}`;
const asWon = won => won == null ? '—' : `${format.format(Math.round(won))}원`;
const delta = wine => wine.awine?.status === 'exact' && wine.yen != null ? wine.awine.price - Math.round(wine.yen * meta.fx.krwPerYen) : null;
const estimatedPercentage = wine => wine.awine?.estimated && wine.yen != null ? 100 * (wine.awine.price - Math.round(wine.yen * meta.fx.krwPerYen)) / wine.awine.price : null;
const percentage = wine => delta(wine) == null ? null : 100 * delta(wine) / wine.awine.price;
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
$('stats').innerHTML = [stat(wines.length, '수집한 와인·세트'), stat(meta.exact, '에이와인 동일 조건'), stat(meta.reference, '에이와인 참고가')].join('');
$('basis').innerHTML = `공식몰 전체 표시 ${format.format(meta.catalogTotal ?? 0)}개 · 확인한 고유 상품 ${format.format(meta.listingCount)}개 · 상품 상세 ${format.format(meta.detailsCount)}개${meta.memberOnly ? ` · 상세 회원 전용 ${format.format(meta.memberOnly)}개` : ''}${meta.detailsUnavailable ? ` · 상세 미확인 ${format.format(meta.detailsUnavailable)}개` : ''} · 에이와인 상세 ${format.format(meta.awinePages)}개. 미확인 가격이나 상품 정보는 갱신 시 반영됩니다. 환율 ${escapeHTML(meta.fx.date)} 기준. <a href="${escapeHTML(meta.fx.url)}" target="_blank" rel="noopener">환율 출처 ↗</a>`;
options('country', unique(wines.map(wine => wine.country)).sort(collator.compare).map(country => [country, country]));
options('region', unique(wines.map(wine => wine.region)).sort(collator.compare).map(region => [region, region]));
options('vintage', unique(wines.map(wine => wine.vintage)).sort((a, b) => b.localeCompare(a)).map(vintage => [vintage, vintage]));
options('volume', unique(wines.map(wine => wine.volume)).sort((a, b) => a - b).map(ml => [ml, `${format.format(ml)} mL`]));
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
  'yen-asc':numericOrder(wine => wine.yen), 'yen-desc':numericOrder(wine => wine.yen, -1),
  'awine-asc':numericOrder(wine => wine.awine?.price), oldest:numericOrder(numericYear) };
function applyFilters() {
  const current = Object.fromEntries(Object.entries(filters).map(([name, el]) => [name, el.value]));
  const terms = current.search.split(/\s+/).map(norm).filter(Boolean);
  filtered = wines.filter(wine =>
    (!kind || wine.type === kind) &&
    (!$('saved-only').checked || saved.has(wine.id)) &&
    (!current.country || wine.country === current.country) &&
    (!current.region || wine.region === current.region) &&
    (!current.vintage || (current.vintage === 'old' ? numericYear(wine) != null && numericYear(wine) < 2010 : wine.vintage === current.vintage)) &&
    (!current.volume || wine.volume === Number(current.volume)) &&
    (!current.comparison || (wine.awine?.status || 'unmatched') === current.comparison) &&
    (!current.stock || (wine.onlineStock || 'unknown') === current.stock) &&
    (!current.min || (wine.yen != null && wine.yen >= Number(current.min))) &&
    (!current.max || (wine.yen != null && wine.yen <= Number(current.max))) &&
    terms.every(term => searchKeys.get(wine.id).includes(term))
  );
  const sort = sorts[$('sort').value];
  if (sort) filtered.sort(sort);
  visible = pageSize;
  render();
}
function card(wine) {
  const main = wine.awine?.name || wine.en || wine.jp;
  const subtitle = wine.jp !== main ? `<p class="jp" lang="ja">${escapeHTML(wine.jp)}</p>` : '';
  const details = [labels[wine.type], wine.pack ? `${wine.pack}병` : '', wine.country, wine.region, wine.vintage, wine.volume ? `${wine.volume}mL` : '', ['out','member'].includes(wine.onlineStock) ? stockText[wine.onlineStock] : ''].filter(Boolean);
  const won = wine.yen == null ? '—' : asWon(wine.yen * meta.fx.krwPerYen);
  const pct = percentage(wine) ?? estimatedPercentage(wine);
  const hint = pct != null ? `<small class="${pct >= 0 ? 'saving' : 'premium'}">${wine.awine.estimated ? '참고 ' : ''}${Math.abs(pct).toFixed(1)}% ${pct >= 0 ? '저렴' : '높음'}</small>` : wine.awine ? '<small>참고가</small>' : '';
  return `<article class="wine"><div><h3>${escapeHTML(main)}</h3>${subtitle}<p class="meta">${details.map(value => `<span>${escapeHTML(value)}</span>`).join('')}</p></div>
    <dl class="prices"><div><dt>타카무라 온라인가</dt><dd>${asYen(wine.yen)}<small>${won}</small></dd></div>
    <div><dt>에이와인</dt><dd>${asWon(wine.awine?.price)}${hint}</dd></div></dl>
    <div class="wine-actions"><button class="secondary" type="button" data-detail="${wine.id}">상세</button><button class="secondary" type="button" data-save="${wine.id}" aria-pressed="${saved.has(wine.id)}">${saved.has(wine.id) ? '찜 해제' : '찜'}</button></div></article>`;
}
function render() {
  const shown = Math.min(visible, filtered.length);
  $('count').textContent = `${format.format(filtered.length)}건${shown < filtered.length ? ` 중 ${format.format(shown)}건 표시` : ''}`;
  $('results').innerHTML = filtered.slice(0, visible).map(card).join('');
  $('more').hidden = shown >= filtered.length;
  $('empty').hidden = filtered.length > 0;
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
  const heading = match?.name || wine.en || wine.jp;
  const japanese = heading !== wine.jp ? `<p lang="ja">${escapeHTML(wine.jp)}</p>` : '';
  $('detail-content').innerHTML = `<h2 id="detail-title">${escapeHTML(heading)}</h2>${japanese}
    <p class="muted">${[wine.id, wine.producer, wine.area, wine.vintage, wine.volume ? `${wine.volume}mL` : ''].filter(Boolean).map(escapeHTML).join(' · ')}</p>
    <h3>타카무라 플러스</h3><p>${asYen(wine.yen)} · ${asWon(wine.yen == null ? null : wine.yen * meta.fx.krwPerYen)} · ${stockText[wine.onlineStock] || '온라인 재고 미확인'}</p>
    <p>에도보리 매장 재고와 판매가 확인 필요${product ? ` · <a target="_blank" rel="noopener" href="${product}">공식몰 상품 ↗</a>` : ''}</p>
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
  Object.values(filters).forEach(el => { el.value = ''; }); setType(''); $('saved-only').checked = false; applyFilters();
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
