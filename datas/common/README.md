# datas/common — 팀 공통 데이터 도구

팀원마다 원본 데이터는 달라도, 결과는 모두 같은 형식(`schema.py`의 `Place`, `Label`)으로 맞춘다.
모든 명령은 **저장소 루트**에서 `uv run python datas/common/<도구>.py ...`로 실행한다.

```
datas/
  common/                  공통 코드, 팀 공유 분할(split.json, 커밋함)
  <이니셜>/                내 폴더 (예: cjm, lkh)
    in/                    내 원본 데이터 (JSON, 숙박 CSV 등) — 커밋하지 않음
    out/                   공통 형식 결과 — 커밋하지 않음
      places_{hotel,restaurant,attraction}.json
      real_reviews.jsonl   원본에 리뷰가 있었다면
      runs/<실행 이름>/     합성 리뷰 · Silver · Gold
```

## 0. 처음 한 번

```bash
uv sync                          # 파이썬 의존성
ollama pull gemma4:e4b           # 로컬 LLM (Silver 생성에 필요, https://ollama.com)
mkdir -p datas/<이니셜>/in       # 내 폴더
```

TourAPI로 새로 수집할 때만 저장소 루트의 `.env`에 키를 넣는다 (`.env`는 커밋하지 않는다).

```
TOUR_API_BASE_URL=https://apis.data.go.kr/B551011/KorService2
TOUR_API_KEY=...
ATTRACTION_URL=...                 # 부산광역시 명소 API
ATTRACTION_API_KEY=...
POPULAR_RESTAURANT_URL=...         # 부산광역시 맛집 API
POPULAR_RESTAURANT_API_KEY=...
```

## 1. 내 데이터를 공통 형식으로 (둘 중 하나)

두 방법 모두 `out/places_*.json`에 쓴다. **한 사람이 둘 다 쓰면 나중에 실행한 쪽이 덮어쓴다.**

### A. 이미 모은 JSON이 있을 때 — `normalize.py`

`in/`에 JSON을 넣고 실행한다.

```bash
uv run python datas/common/normalize.py <이니셜>     # 이니셜을 빼면 모든 팀원
```

필드 이름이 달라도 흔한 이름은 알아서 맞춘다. 예를 들어 아래 둘 다 읽힌다.

```json
[{"location_id": "10423568", "name": "켄트호텔 광안리", "category": "HOTEL", "regions": ["광안리"],
  "reviews": [{"review_id": "1064242022", "text": "해변 바로 앞이고 ...", "rating": 4}]}]
```

```json
{"places": [{"contentid": "2872583", "title": "우남정", "contenttypeid": "39",
             "addr1": "부산광역시 기장군 철마면 곰내길 115", "mapy": "35.30", "mapx": "129.18"}]}
```

| 공통 필드 | 읽는 원본 필드 |
|---|---|
| `place_id` | `place_id`(이미 `출처:ID`), `location_id`→`tripadvisor:`, `contentid`→`tourapi:`, `UC_SEQ`→`busan:`, `id` |
| `name` / `category` | `name`·`title` / `category`·`contenttypeid` (`HOTEL`·`숙박`·`32` → hotel 등) |
| `district` | 주소의 구·군 → `district`·`regions` 값 → 동네 이름(광안리 → suyeong) |
| `lat` / `lng` | `lat`·`latitude`·`mapy` / `lng`·`longitude`·`mapx` |
| `facts` | `facts` 객체, 없으면 나머지 단순 값 필드 |

- 장소 안의 `reviews`는 `out/real_reviews.jsonl`로 옮긴다 (`synthetic: false`). 번역된 리뷰는 `translated: true`로 표시한다.
- ID·이름·카테고리가 없는 레코드는 건너뛰고 이유를 보여준다.

### B. 새로 수집할 때 — `collect_places.py` (TourAPI·부산시 API·숙박 CSV)

```bash
uv run python datas/common/collect_places.py --member <이니셜> --districts suyeong nam --dry-run
uv run python datas/common/collect_places.py --member <이니셜> --districts suyeong nam
```

- TourAPI는 **하루 1,000회 한도**가 있다. 반드시 `--dry-run`으로 호출 수를 먼저 본다. 받은 응답은 `out/cache/`에 저장해 다시 부르지 않는다.
- 숙박 CSV는 내 폴더 아래의 `*숙박*.csv`를 찾아 읽는다 (UTF-8·CP949 자동).
- 구·군 id: `jung seo dong yeongdo busanjin dongnae nam buk haeundae saha geumjeong gangseo yeonje suyeong sasang gijang`

## 2. Silver 만들기 — `make_silver.py`

```bash
uv run python datas/common/make_silver.py --member <이니셜> --run pilot \
    --category hotel restaurant attraction --count 34
```

- 내 장소로 합성 리뷰 생성 → gemma4가 라벨 → 자동 검사를 한 번에 한다. 결과는 `out/runs/pilot/`.
- 멈춰도 **같은 명령으로 이어서** 한다. 텍스트가 깨진 리뷰(`<0xEB>` 등)는 seed를 바꿔 다시 만들고, 끝내 깨지면 저장하지 않는다.
- 한 건에 5초 안팎. 먼저 적은 수(`--count 34`)로 확인한 뒤 늘린다.

## 3. 분할과 Gold 검수

```bash
uv run python datas/common/split_places.py --member <이니셜> --run pilot
uv run python datas/common/review_gold.py datas/<이니셜>/out/runs/pilot/test/silver.jsonl --reviewer <이름>
```

- **분할**: 팀 전체가 `common/split.json` 하나를 쓴다. 이미 배정된 장소는 바뀌지 않고 새 장소만 배정된다 (장소 단위 80/10/10). 바뀐 `split.json`은 **커밋해서 공유**한다.
- **검수**: 브라우저가 열린다. 리뷰를 먼저 읽고, 라벨을 고쳐 **⌘/Ctrl+Enter로 승인**하거나 리뷰가 이상하면 **버린다**. 기준은 `docs/annotation-guideline.md` 7절.
- **결과**: `test/gold.jsonl`(승인, `tier: gold`, 원래 Silver 라벨은 `silver_label`) · `test/discarded.jsonl`(버림). 결정할 때마다 저장되고, 같은 명령으로 이어서 한다.

## 4. 실제 리뷰에 라벨 달기 (선택)

`normalize.py`가 만든 `out/real_reviews.jsonl`도 같은 도구로 Silver·Gold를 만들 수 있다.

```bash
uv run python datas/common/extract_labels.py datas/<이니셜>/out/real_reviews.jsonl --out datas/<이니셜>/out/runs/real/labeled.jsonl
uv run python datas/common/label_check.py datas/<이니셜>/out/runs/real/labeled.jsonl --out datas/<이니셜>/out/runs/real/silver.jsonl
uv run python datas/common/review_gold.py datas/<이니셜>/out/runs/real/silver.jsonl --reviewer <이름>
```

번역 리뷰(`translated: true`)는 실제 한국어 문체가 아니므로 평가할 때 따로 본다.

## 도구 목록

| 파일 | 역할 |
|---|---|
| `schema.py` | 장소·라벨 형식, 허용값, 부산 구·군 |
| `paths.py` | 팀원 폴더 규칙, 팀 전체 장소 읽기 |
| `normalize.py` | 원본 JSON → 공통 형식 |
| `collect_places.py` | TourAPI·부산시 API·숙박 CSV 수집 |
| `generate_reviews.py` | 합성 리뷰 생성 (make_silver가 부른다) |
| `extract_labels.py` | 라벨 추출: 리뷰는 gemma4, 장소 근거는 규칙 |
| `label_check.py` | Silver 자동 검사 |
| `make_silver.py` | 생성 → 라벨 → 검사를 한 번에 |
| `split_places.py` | 팀 전체 장소 분할, Gold 검수 대기 파일 |
| `review_gold.py` + `.html` | 브라우저 검수 화면 |
| `ollama_client.py` | 로컬 Ollama 호출 |
