# Streamlit UI 시스템 설계서
> 환경시설 관급자재 공급망 의사결정 모델 — 시각화·인터랙션 계층

| 항목 | 내용 |
|---|---|
| 작성 목적 | UI(Streamlit) 팀과 모델링·스코어링 팀 간 **역할 경계와 인터페이스 계약**을 명확히 하여 중복 개발과 오해를 제거 |
| 대상 독자 | 스코어링/모델링 담당 팀원 (`시스템 구현.py`, `공급망.py`, `final.csv` 관리 책임자) |
| 작성자 역할 | Streamlit UI 구현·시각화 담당 |
| 관련 문서 | `시스템 설계서.md`, `시스템 skeleton.py`, `시스템 구현.py` |

---

## 1. 한 페이지 요약

> **모델링 팀이 만든 `SupplyChainEngine`을 UI가 그대로 호출해서, 발주 담당자가 마우스로 조작 가능한 의사결정 화면을 만든다.**
>
> UI는 **점수 로직을 다시 짜지 않는다.** 모델링 팀의 코드를 *사용자 친화적으로 노출*하는 얇은 프레젠테이션 레이어다.
> 단, **가중치 동적 변경**과 **품명번호 카탈로그**는 UI에서 필수이므로, 모델링 팀에 두 가지 API 보강을 요청한다 (§4 참조).

---

## 2. 역할 분담 매트릭스

| 영역 | 모델링/스코어링 팀 | UI(Streamlit) 팀 |
|---|---|---|
| 데이터 전처리 (업체별_정보 + cluster.csv 결합) | ✅ 책임 | ❌ 사용만 함 |
| `final.csv` 스키마 유지·갱신 | ✅ 책임 | ❌ |
| 4점수(실적·사회·안정성·적합성) 정의·계산 로직 | ✅ 책임 | ❌ |
| KMeans 클러스터링 학습 | ✅ 책임 | ❌ |
| `SupplyChainEngine` 클래스 인터페이스 | ✅ 책임 | ❌ (호출만) |
| 가중치 슬라이더 인터랙션 | ❌ | ✅ |
| 품목 드롭다운/검색 UX | ❌ | ✅ |
| 결과 표·차트·지도 시각화 | ❌ | ✅ |
| 다운로드(CSV/PDF) UI | ❌ | ✅ |
| 발주 시나리오 비교 화면 | ❌ | ✅ |
| 보고서 자동 생성 | (현행 `generate_report.py` 유지) | UI에서 트리거만 |

---

## 3. UI가 구현할 것 (In-Scope)

### 3.1 페이지 구조 (4 Tab)

```
┌─────────────────────────────────────────────────────────────┐
│ [헤더]  환경시설 관급자재 공급망 의사결정 모델              │
├─────────────────────────────────────────────────────────────┤
│ ┌──[사이드바]──┐ ┌──[메인 영역]─────────────────────────┐ │
│ │ 발주 입력    │ │ ╔═Tab1═╦═Tab2═╦═Tab3═╦═Tab4═════╗ │ │
│ │  • 품명검색  │ │ ║ 추천 ║가중치║클러  ║ 업체상세 ║ │ │
│ │  • 예산 입력 │ │ ║ 결과 ║시뮬  ║스터  ║          ║ │ │
│ │  • Top-K     │ │ ╚══════╩══════╩══════╩══════════╝ │ │
│ │              │ │                                    │ │
│ │ 가중치 조정  │ │  (선택된 탭 내용)                  │ │
│ │  • 실적 ▬▬▬ │ │                                    │ │
│ │  • 사회 ▬▬▬ │ │                                    │ │
│ │  • 안정 ▬▬▬ │ │                                    │ │
│ │  • 적합 ▬▬▬ │ │                                    │ │
│ └──────────────┘ └────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 탭별 기능 명세

**Tab 1 — 추천 결과 (메인 화면)**
- 입력 요약 카드 (품목명·예산·Top-K)
- Top-K 업체 표 (제출 양식 컬럼 그대로: 순위·업체명·사업자번호·대표자명·주소·지표합·지표명·4점수·종합점수)
- 행 클릭 → Tab 4(업체 상세)로 이동
- "결과 CSV 다운로드" 버튼
- "이 결과로 보고서 생성" 버튼 → `generate_report.py` 트리거 (백그라운드)

**Tab 2 — 가중치 시뮬레이터**
- 사이드바 슬라이더(0~100%)로 4점수 가중치 실시간 조정 (합계 자동 정규화 표시)
- 가중치 변경 즉시 Top-K 재산출 (Streamlit reactive)
- "기본값(25/30/20/25) 복원" 버튼
- **Before/After 비교 표:** 기본 가중치 Top10 vs 사용자 가중치 Top10 (순위 변동 화살표 표시)
- 핵심 시나리오 프리셋 버튼: "사회적 가치 최우선(50/15/15/20)", "실적 최우선(40/20/20/20)", "균형(25/25/25/25)"

**Tab 3 — 클러스터 / 모집단 분석**
- KMeans 클러스터 산점도 (PCA 2D 투영, 색=cluster_label)
- 추천된 Top-K 업체를 산점도 위에 별표로 강조
- 4,003개 환경 업체의 4점수 히스토그램 (사용자 입력 결과 위치 마커)
- 시도별 분포 지도 (Plotly choropleth, 부울경 강조)
- 사회 지표 보유 분포 도넛 차트

**Tab 4 — 업체 상세**
- 선택 업체 1개에 대한 상세 카드
  - 기본 정보 (업체명·대표·주소·전화-N/A·업종)
  - 4점수 레이더 차트
  - 환경 분야 낙찰 이력 (`환경_공고명목록` 그대로 표시 — 검증 자료로 핵심)
  - 사회 지표 보유 현황
  - 클러스터 라벨 + 클러스터 평균 대비 위치
- "이 업체를 추천 풀에서 제외하고 다시 계산" 버튼 (제재 의심 등 수동 컨트롤)

### 3.3 사이드바 입력 컴포넌트
- 품목 검색: `st.selectbox` + 키워드 검색 (대표세부품명 라벨 표시, 내부적으로는 세부품명번호 전달)
- 예산: `st.number_input` (원 단위, 천 단위 콤마 포맷)
- Top-K: `st.slider` (5~50, 기본 20)
- Strict filter 토글: `st.toggle` (기본 ON)
- 가중치 슬라이더 4종

### 3.4 공통 UX 요구사항
- 모든 점수는 0~100 게이지 또는 컬러 칩으로 표시 (숫자만 아님)
- 한글 깨짐 방지 (Plotly font: "AppleGothic" / "NanumGothic" fallback)
- 캐시: `@st.cache_resource`로 엔진 1회 로드 (4,003행 매번 재처리 방지)
- 모바일은 미지원 (데스크탑/태블릿 가로 모드 가정)

---

## 4. 모델링 팀에 요청하는 인터페이스 (Contract)

> **이 절이 본 문서에서 가장 중요합니다. 두 가지 API 보강을 요청합니다.**

### 4.1 [현행 유지] `SupplyChainEngine.recommend()` 시그니처 고정

UI는 다음 시그니처에 의존합니다. **인자 추가는 OK, 기존 인자 제거·이름 변경 시 사전 공지 필수.**

```python
engine.recommend(
    detail_item_no: int,
    budget: float,
    top_k: int = 20,
    strict_filter: bool = True,
) -> pd.DataFrame
```

반환 DataFrame 컬럼 (현행 그대로 유지 부탁):
```
순위, 업체명, 사업자번호, 대표자명, 주소, 지표합, 지표명,
실적점수, 사회점수, 안정성점수, 적합성점수, 종합점수
```

### 4.2 [요청 #1] `weights` 인자 추가 — 가중치 시뮬레이터 필수

현재는 `WEIGHTS` 상수가 하드코딩되어 있어 UI에서 변경 불가능합니다. **다음과 같이 옵션 인자를 추가**해 주세요.

```python
def recommend(
    self,
    detail_item_no: int,
    budget: float,
    top_k: int = 20,
    strict_filter: bool = True,
    weights: dict | None = None,    # ★ 추가 요청
) -> pd.DataFrame:
    w = weights or WEIGHTS
    # 합계가 1.0이 아니면 자동 정규화 (또는 ValueError) 결정 필요
    ...
    종합점수 = w["performance"]*P + w["social"]*S + w["stability"]*T + w["fit"]*F
```

UI에서 사용 예:
```python
result = engine.recommend(
    item, budget,
    weights={"performance": 0.40, "social": 0.20, "stability": 0.20, "fit": 0.20}
)
```

**결정 요청:** 가중치 합이 1.0 아닐 때 → ① 자동 정규화 vs ② ValueError 발생 — 어느 쪽으로 할지 회신 부탁 (UI 기본값은 자동 정규화 + 사용자에게 합계 표시).

### 4.3 [요청 #2] 품명번호 카탈로그 함수 — 드롭다운 검색 필수

UI 사이드바에서 발주 담당자가 *"수중펌프"*라고 검색하면 자동완성으로 *세부품명번호 4015151301*이 채워져야 합니다. 다음 헬퍼를 엔진 또는 별도 모듈에 추가해 주세요.

```python
def get_item_catalog(self) -> pd.DataFrame:
    """검색·드롭다운용 품명 카탈로그.

    Returns:
        DataFrame[세부품명번호, 대표세부품명, 후보업체수, 평균예산]
        후보업체수: 해당 품명번호를 대표품목으로 가진 업체 수
        평균예산:    해당 품명의 환경_낙찰금액평균 중앙값
    """
```

UI는 이 결과를 `st.selectbox` 옵션 + 예산 기본값 자동 채우기에 사용.

### 4.4 [선택 요청 #3] 클러스터 메타데이터 — Tab 3에 필요

PCA 투영 좌표를 매번 UI에서 계산하지 않도록, 사전 계산된 좌표를 final.csv에 추가해 주시면 좋습니다 (없으면 UI에서 즉석 계산).

```
컬럼명: pca_x, pca_y      (4점수의 PCA 2차원 투영)
```

### 4.5 [선택 요청 #4] 단위 테스트 보강

UI 작업 중 모델 변경이 잦을 수 있어, 다음 회귀 테스트를 모델 팀에서 유지해 주시면 좋습니다.
- 동일 입력 (수중펌프 4015151301, 9천만원) → Top 1 업체가 변하지 않는다
- 가중치 (1, 0, 0, 0) → 실적점수 단독 정렬과 일치한다

### 4.6 데이터 계약 — `final.csv` 스키마

UI는 다음 컬럼이 final.csv에 **반드시 존재**한다고 가정합니다. 컬럼 이름·dtype 변경 시 사전 공지 부탁.

| 컬럼 | dtype | 용도 |
|---|---|---|
| `bizno` | str (10-digit) | PK |
| `업체명`, `대표자명`, `주소` | str | 표시 |
| `대표세부품명번호`, `대표세부품명` | float, str | 카탈로그 |
| `환경_낙찰건수`, `환경_낙찰금액합`, `환경_낙찰금액평균`, `환경_평균낙찰률`, `환경_최근낙찰일` | numeric/date | 실적·적합성 점수 |
| `환경_공고명목록` | str (list-like) | Tab 4 검증자료 |
| `자활용사촌_YN`, `사회적기업_YN`, `장애인기업_YN`, `여성기업_YN`, `사회적책임_지표합` | str/int | 사회 점수·라벨 |
| `active_years`, `demand_org_count`, `recent_1y_bid_count` | numeric | 안정성 점수 |
| `cluster_label` | int (0/1) | Tab 3 시각화 |

---

## 5. UI가 구현하지 않을 것 (Out-of-Scope)

> **모델링 팀 책임 영역. UI는 이 부분을 다시 만들지 않습니다.**

| 비구현 항목 | 책임 위치 |
|---|---|
| 점수 계산 로직 (P/S/T/F) | `시스템 구현.py` |
| KMeans 학습·실루엣 k 선택 | `공급망.py` |
| 데이터 전처리 / 결합 / 정제 | (별도 ETL) → `final.csv` |
| 부정당제재·인증 데이터 갱신 | 모델링 팀 (외부 API/CSV) |
| 결과 보고서(.docx) 생성 | 기존 `generate_report.py` 유지 |
| 가중치 정책의 적정성 검증 | 모델링 팀 + 기관 협의 |
| 추천 결과의 사후 평가 (ground-truth 비교) | 모델링 팀 |

UI는 위 항목들의 **결과를 받아 표시**할 뿐, 로직을 재구현하지 않습니다.

---

## 6. 데이터 플로우 / 아키텍처

```
┌────────────────────────────────────────────────────────────┐
│  [데이터 레이어]                                            │
│   final.csv  ←  업체별_정보.csv ⊕ cluster.csv  (모델팀)    │
└──────────────────────────┬─────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────┐
│  [모델 레이어]  시스템 구현.py                              │
│   SupplyChainEngine                                        │
│     .load()                                                │
│     .recommend(item, budget, top_k, strict, weights=...)   │
│     .get_item_catalog()           ★ 신규 요청              │
└──────────────────────────┬─────────────────────────────────┘
                           │  (Python 함수 호출만)
┌──────────────────────────▼─────────────────────────────────┐
│  [UI 레이어]  app.py (Streamlit)                            │
│   - st.cache_resource로 엔진 1회 로드                      │
│   - 사이드바 입력 ──► engine.recommend() ──► 표·차트 렌더  │
│   - 가중치 슬라이더 변경 시 reactive 재계산                │
└────────────────────────────────────────────────────────────┘
```

---

## 7. 기술 스택 / 의존성

| 항목 | 선택 |
|---|---|
| 프레임워크 | Streamlit ≥ 1.30 |
| 차트 | Plotly (인터랙티브, 한글 지원) — 보조로 Altair |
| 표 | `st.dataframe` (정렬·필터 지원) |
| 지도 | Plotly choropleth + Folium (선택) |
| 폰트 | NanumGothic / AppleGothic |
| 캐싱 | `@st.cache_resource` (엔진), `@st.cache_data` (카탈로그) |
| 배포 | 로컬 시연(`streamlit run app.py`) → 추후 Streamlit Cloud 가능 |

```bash
pip install streamlit plotly pandas numpy scikit-learn
```

---

## 8. 마일스톤

| 단계 | 산출물 | 의존성 |
|---|---|---|
| **M1**: 모델 팀 → UI 팀 인터페이스 확정 | `recommend(weights=)` + `get_item_catalog()` | 모델 팀 |
| M2: UI 골격 (Tab 1만) 구현 | `app.py` 초안 | M1 |
| M3: 가중치 시뮬레이터(Tab 2) | 슬라이더 + 비교 표 | M1, M2 |
| M4: 클러스터 시각화(Tab 3) | PCA 산점도 + 분포 차트 | M2 |
| M5: 업체 상세(Tab 4) + 다운로드 | 레이더 차트 + CSV/보고서 | M2 |
| M6: 발표용 데모 시나리오 리허설 | 슬라이드+라이브 데모 | M5 |

**현재 차단 요소(Blocker):** §4.2, §4.3 — 모델 팀의 API 보강 회신을 기다림.

---

## 9. 모델 팀에 던지는 결정 요청 체크리스트

UI 구현 시작 전에 회신 부탁드리는 항목입니다.

- [ ] **Q1.** `recommend(weights=...)` 인자 추가 가능한가? (필수)
- [ ] **Q2.** 가중치 합 ≠ 1.0 일 때 정책: ① 자동 정규화 ② 예외 발생 — 어느 쪽?
- [ ] **Q3.** `get_item_catalog()` 헬퍼 추가 가능한가? 또는 UI에서 final.csv 직접 집계해도 무방한가?
- [ ] **Q4.** PCA 좌표(`pca_x`, `pca_y`)를 final.csv에 추가해 주실 수 있는가? (없으면 UI에서 매번 계산 — 약간의 성능 손해)
- [ ] **Q5.** "이 업체 제외하고 재계산" 기능을 UI에서 구현해도 되는가? (모델 팀의 추천 일관성 정책에 영향)
- [ ] **Q6.** `cluster_label` 의미 라벨을 정해 주실 수 있는가? (예: 0=`활성검증풀`, 1=`신생저활동풀`) — UI 표시 통일용

---

## 10. 부록 — 참조 코드 스니펫

### 10.1 UI에서 엔진 호출 (Streamlit pseudocode)

```python
import streamlit as st
import importlib.util
from pathlib import Path

@st.cache_resource
def load_engine():
    spec = importlib.util.spec_from_file_location(
        "engine_mod",
        Path(__file__).parent / "시스템 구현.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SupplyChainEngine.load()

engine = load_engine()

# 사이드바
with st.sidebar:
    catalog = engine.get_item_catalog()    # ★ 모델 팀 요청 #2
    item_label = st.selectbox(
        "세부품명",
        catalog["대표세부품명"],
        index=0,
    )
    item_no = catalog.loc[catalog["대표세부품명"] == item_label, "세부품명번호"].iloc[0]

    budget = st.number_input("추정금액(원)", min_value=0, value=100_000_000, step=10_000_000)
    top_k = st.slider("Top-K", 5, 50, 20)

    st.divider()
    st.subheader("가중치 조정")
    w_p = st.slider("실적", 0, 100, 25)
    w_s = st.slider("사회", 0, 100, 30)
    w_t = st.slider("안정성", 0, 100, 20)
    w_f = st.slider("적합성", 0, 100, 25)
    total = w_p + w_s + w_t + w_f
    weights = {
        "performance": w_p/total, "social": w_s/total,
        "stability":  w_t/total, "fit":    w_f/total,
    }
    st.caption(f"합계 {total} → 자동 정규화")

# 추천 호출
result = engine.recommend(
    detail_item_no=int(item_no),
    budget=budget,
    top_k=top_k,
    weights=weights,        # ★ 모델 팀 요청 #1
)
st.dataframe(result, use_container_width=True)
```

---

## 11. 변경 이력

| 일자 | 버전 | 변경 내용 | 작성자 |
|---|---|---|---|
| 2026-05-03 | v0.1 | 초안 작성, 모델 팀에 API 보강 2건 요청 | UI 팀 |
