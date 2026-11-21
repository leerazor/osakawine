# 오사카 타카무라 와인 가격 비교

오사카 에도보리점 방문 전에 와인을 고르는 대시보드입니다. 일본 소비세가 포함된 타카무라 플러스 온라인 표시가를 한국 판매처의 공개 가격과 대조합니다. 에도보리 실매장의 재고와 가격은 매장에 확인해야 합니다.

`index.html`을 브라우저에서 열면 검색, 필터, 가격 정렬, 찜 목록과 일본어 문의 문구 복사를 사용할 수 있습니다. 찜 목록은 같은 브라우저에 저장됩니다.

## 비교 기준

- 한국 구매가 대비 절약률·절약액은 동일 와인·빈티지·용량으로 구매할 수 있는 판매가를 기준으로 계산합니다. 검증한 판매가가 여럿이면 가장 낮은 값을 사용합니다. 한국 직구는 세금과 배송비가 확인된 총액을 비교합니다.
- 빈티지·용량 미확인, 품절, 주문 후 재고 확인, 공동구매, 직구 총액 미확인 가격은 참고가로 표시합니다. 한국 구매가 정렬에서 참고가만 있는 상품과 가격 미확인 상품은 뒤에 배치합니다.
- 영문 와인명, 빈티지, 용량이 일치하면 동일 조건으로 표시합니다. 상품 상세에서 확인한 에이와인 가격을 기준으로 원화 절약액과 절약률을 계산합니다.
- 가까운 빈티지나 품절가는 참고가입니다. 타카무라 용량이 750mL로 표시되고 에이와인의 용량 표기만 없는 동일 빈티지는 750mL 가정 비교를 지원합니다. 페이지 상세에서 가정과 근거를 볼 수 있습니다.
- 재대조에서는 2009년 이전 와인에 대해 에이와인의 빈티지가 미표기된 가격을 제외합니다.
- 세트 구성품이 확인되면 에이와인 단품 가격에 병 수를 곱해 합산합니다. 구성품이나 가격을 확인하기 어려운 세트에는 타카무라 표시가를 제공합니다.
- 환율에는 환전·결제 수수료와 한국 반입 비용이 포함되지 않습니다. 가격 수집 기준일과 환율을 페이지에서 확인할 수 있습니다.

## 데이터 갱신

Python 3.10 이상, `lxml`, `curl`이 필요합니다. 새 스냅샷은 빈 캐시 폴더를 사용합니다. 조회가 일시적으로 실패한 항목은 같은 캐시로 다시 실행할 수 있습니다. `compare.py`의 `PRICE_RATE`에는 비교 기준 환율과 출처를 설정합니다.

```sh
python -m pip install lxml
python collect.py catalog --cache workdata
python collect.py takamura --cache workdata
python collect.py awine-index --cache workdata
python compare.py candidates --cache workdata
python collect.py awine-details --cache workdata
python compare.py build --cache workdata --output workdata/dashboard.json
python render.py --data workdata/dashboard.json --output index.html
```

기존 스냅샷에서 에이와인 후보를 찾지 못한 단품은 아래 명령으로 다시 확인합니다. 후보는 사이트맵의 영문 표기에서 찾고, 비교에는 상품 상세에 표시된 이름·빈티지·용량·가격을 사용합니다.

```sh
python prepare_recheck.py --snapshot workdata/dashboard.json --cache workdata --output workdata/recheck
python collect.py awine-details --cache workdata/recheck
python compare.py build --cache workdata --recheck-cache workdata/recheck --output workdata/dashboard-rechecked.json
python render.py --data workdata/dashboard-rechecked.json --output index.html
```

데일리샷·굿딜와인·키햐의 공개 상품 상세에서 이름, 빈티지, 용량, 재고, 결제 기준 가격을 읽고 한국 구매가를 붙입니다. `compare_korea.py`의 `read_offer()`로 상품 HTML을 읽은 결과를 `offers` 배열에 저장하면 아래 명령을 실행할 수 있습니다. `compare_korea.py`는 기존 스냅샷에서 에이와인 비교가가 비어 있던 항목을 대조합니다.

```sh
python compare_korea.py --snapshot workdata/dashboard-rechecked.json --offers workdata/korean-offers.json --output workdata/dashboard-korea.json
python render.py --data workdata/dashboard-korea.json --output index.html
```

GitHub Pages의 게시 소스를 `main` 브랜치 루트로 설정하면 `index.html`을 게시할 수 있습니다.
