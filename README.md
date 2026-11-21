# 오사카 타카무라 와인 가격 비교

오사카 에도보리점 방문 전에 와인을 고르는 대시보드입니다. 일본 소비세가 포함된 타카무라 플러스 온라인 표시가를 에이와인 상품 상세 페이지의 공개 가격과 대조합니다. 에도보리 실매장의 재고와 가격은 매장에 확인해야 합니다.

`index.html`을 브라우저에서 열면 검색, 필터, 가격 정렬, 찜 목록과 일본어 문의 문구 복사를 사용할 수 있습니다. 찜 목록은 같은 브라우저에 저장됩니다.

## 비교 기준

- 영문 와인명, 빈티지, 용량이 일치하면 동일 조건으로 표시합니다. 상품 상세에서 확인한 에이와인 가격을 기준으로 원화 절약액과 절약률을 계산합니다.
- 가까운 빈티지나 품절가는 참고가입니다. 타카무라 용량이 750mL로 표시되고 에이와인의 용량 표기만 없는 동일 빈티지는 750mL 가정 비교를 지원합니다. 페이지 상세에서 가정과 근거를 볼 수 있습니다.
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

GitHub Pages의 게시 소스를 `main` 브랜치 루트로 설정하면 `index.html`을 게시할 수 있습니다.
