"""공급망 의사결정 모델 — 스코어링 프로토타입 (실행본)

설계서: model_prototype_설계서.md
골격: model_prototype_skeleton.py

실행:
    python3 model_prototype.py
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


DATA_DIR = Path("/Users/leeyoungjoon/Documents/공모전")
INPUT_CSV = DATA_DIR / "output_final_supply_chain_improved.csv"
RAW_FILES = [DATA_DIR / f"{y}년 나라장터.csv" for y in (2023, 2024, 2025, 2026)]
OUTPUT_CLUSTERS = DATA_DIR / "output_model_prototype_clusters.csv"
OUTPUT_RECS = DATA_DIR / "output_model_prototype_recommendations.csv"

WEIGHTS = {
    "performance": 0.30,
    "social": 0.30,
    "stability": 0.15,
    "fitness": 0.20,
}
RISK_PENALTY = 0.05
CLUSTER_K = 5
RANDOM_STATE = 42

CLUSTER_FEATURES = [
    "실적_건수_log", "실적_금액_log", "실적_최신성",
    "사회적책임_지표합",
    "자활용사촌_num", "여성기업_num", "장애인기업_num", "사회적기업_num",
    "환경_집중도", "실적_지속성",
]

SOCIAL_LABEL_MAP = {
    "자활용사촌_YN": "자활용사촌",
    "여성기업_YN": "여성기업",
    "장애인기업_YN": "장애인기업",
    "사회적기업_YN": "사회적기업",
}


def build_features(df: pd.DataFrame, today: datetime | None = None) -> pd.DataFrame:
    df = df.copy()
    today = today or datetime.now()

    df["실적_건수_log"] = np.log1p(df["환경_낙찰건수"])
    df["실적_금액_log"] = np.log1p(df["환경_낙찰금액합"])
    df["환경_최근낙찰일"] = pd.to_datetime(df["환경_최근낙찰일"], errors="coerce")
    days_since = (today - df["환경_최근낙찰일"]).dt.days
    df["실적_최신성"] = (1 - days_since / 1095).clip(lower=0, upper=1).fillna(0)

    for yn_col, short in SOCIAL_LABEL_MAP.items():
        df[f"{short}_num"] = (df[yn_col] == "Y").astype(int)

    df["환경_집중도"] = (df["환경_낙찰건수"] / df["전체_낙찰건수"].clip(lower=1)).clip(0, 1)
    df["실적_지속성"] = (df["환경_낙찰건수"] >= 5).astype(int)
    return df


def _assign_personas(centroids: pd.DataFrame) -> dict[int, str]:
    perf = centroids["실적_건수_log"] + centroids["실적_금액_log"]
    social = centroids["사회적책임_지표합"]
    perf_rank = perf.rank(ascending=False)
    social_rank = social.rank(ascending=False)

    persona = {}
    n = len(centroids)
    for cid in centroids.index:
        p, s = perf_rank[cid], social_rank[cid]
        if p <= 2 and s <= 2:
            persona[cid] = "우수공급군"
        elif p <= 2:
            persona[cid] = "대형실적군"
        elif s <= 2:
            persona[cid] = "잠재공급군"
        elif p >= n:
            persona[cid] = "신규/소규모군"
        else:
            persona[cid] = "일반공급군"
    return persona


def fit_clusters(df: pd.DataFrame, k: int = CLUSTER_K) -> tuple[pd.DataFrame, dict]:
    X_raw = df[CLUSTER_FEATURES].fillna(0).to_numpy()
    scaler = StandardScaler()
    X = scaler.fit_transform(X_raw)

    km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
    cluster_ids = km.fit_predict(X)
    df = df.copy()
    df["cluster_id"] = cluster_ids

    centroids = pd.DataFrame(
        scaler.inverse_transform(km.cluster_centers_),
        columns=CLUSTER_FEATURES,
    )
    persona_map = _assign_personas(centroids)
    df["페르소나"] = df["cluster_id"].map(persona_map)

    metrics = {
        "k": k,
        "silhouette": float(silhouette_score(X, cluster_ids)),
        "centroids": centroids,
        "persona_map": persona_map,
    }
    return df, metrics


def compute_scores(df: pd.DataFrame, fitness: pd.Series | None = None) -> pd.DataFrame:
    df = df.copy()

    def _norm(s: pd.Series) -> pd.Series:
        s = s.fillna(0)
        rng = s.max() - s.min()
        return (s - s.min()) / rng if rng > 0 else s * 0

    df["점수_실적"] = (
        0.5 * _norm(df["실적_건수_log"])
        + 0.3 * _norm(df["실적_금액_log"])
        + 0.2 * df["실적_최신성"]
    )
    df["점수_사회적"] = df["사회적책임_지표합"] / 4.0
    df["점수_안정성"] = 0.5 * df["환경_집중도"] + 0.5 * df["실적_지속성"]
    df["점수_적합성"] = fitness if fitness is not None else 0.0
    df["점수_리스크"] = 0.0

    df["종합점수"] = (
        WEIGHTS["performance"] * df["점수_실적"]
        + WEIGHTS["social"] * df["점수_사회적"]
        + WEIGHTS["stability"] * df["점수_안정성"]
        + WEIGHTS["fitness"] * df["점수_적합성"]
        - RISK_PENALTY * df["점수_리스크"]
    )
    return df


def _format_indicators(row: pd.Series) -> str:
    flags = [name for col, name in SOCIAL_LABEL_MAP.items() if row.get(col) == "Y"]
    return ", ".join(flags) if flags else "-"


def recommend_suppliers(
    품목_키워드: str,
    추정금액: float,
    df_clustered: pd.DataFrame,
    raw_lookup: pd.DataFrame,
    top_n: int = 10,
    cluster_filter: list[str] | None = None,
    region: str | None = None,
    require_social: bool = False,
) -> pd.DataFrame:
    matched = raw_lookup[
        raw_lookup["bidNtceNm"].str.contains(품목_키워드, na=False, case=False)
    ]
    candidate_biznos = set(matched["bidwinnrBizno"].dropna().astype("int64"))

    if not candidate_biznos:
        print(f"   [경고] '{품목_키워드}' 관련 낙찰 이력 없음")
        return pd.DataFrame()

    item_stats = (
        matched.groupby("bidwinnrBizno")
        .agg(
            품목_낙찰건수=("bidNtceNo", "count"),
            품목_평균금액=("sucsfbidAmt", "mean"),
        )
        .reset_index()
    )

    work = df_clustered[df_clustered["bidwinnrBizno"].isin(candidate_biznos)].copy()
    work = work.merge(item_stats, on="bidwinnrBizno", how="left")
    work["품목_낙찰건수"] = work["품목_낙찰건수"].fillna(0)
    work["품목_평균금액"] = work["품목_평균금액"].fillna(추정금액)

    max_exp = work["품목_낙찰건수"].max() or 1
    item_exp_norm = np.log1p(work["품목_낙찰건수"]) / np.log1p(max_exp)
    budget_diff = np.abs(
        np.log(work["품목_평균금액"].clip(lower=1)) - np.log(max(추정금액, 1))
    )
    budget_fit = (1 - budget_diff / 5).clip(0, 1)
    work["점수_적합성_동적"] = 0.5 * item_exp_norm + 0.5 * budget_fit

    work = compute_scores(work, fitness=work["점수_적합성_동적"])

    if cluster_filter:
        work = work[work["페르소나"].isin(cluster_filter)]
    if region:
        work = work[work["주소"].str.contains(region, na=False)]
    if require_social:
        work = work[work["사회적책임_지표합"] >= 1]

    work = work.sort_values("종합점수", ascending=False).head(top_n).reset_index(drop=True)
    work["순위"] = work.index + 1
    work["지표명"] = work.apply(_format_indicators, axis=1)
    work["종합점수"] = work["종합점수"].round(4)

    output_cols = [
        "순위", "업체명", "bidwinnrBizno", "대표자명", "주소",
        "사회적책임_지표합", "지표명", "페르소나", "종합점수",
    ]
    return work[output_cols].rename(columns={
        "bidwinnrBizno": "사업자번호",
        "사회적책임_지표합": "지표합",
    })


def load_raw_lookup() -> pd.DataFrame:
    frames = []
    usecols = ["bidNtceNo", "bidNtceNm", "bidwinnrBizno", "sucsfbidAmt"]
    for fp in RAW_FILES:
        f = pd.read_csv(fp, encoding="utf-8-sig", low_memory=False, usecols=usecols)
        frames.append(f)
    raw = pd.concat(frames, ignore_index=True)
    raw["bidwinnrBizno"] = pd.to_numeric(raw["bidwinnrBizno"], errors="coerce")
    raw["sucsfbidAmt"] = pd.to_numeric(raw["sucsfbidAmt"], errors="coerce")
    raw = raw.dropna(subset=["bidwinnrBizno"]).copy()
    raw["bidwinnrBizno"] = raw["bidwinnrBizno"].astype("int64")
    return raw


def main() -> None:
    print("=" * 70)
    print("공급망 의사결정 모델 — 스코어링 프로토타입")
    print("=" * 70)

    print("\n[1/4] 데이터 로드")
    df = pd.read_csv(INPUT_CSV, encoding="utf-8-sig")
    raw = load_raw_lookup()
    print(f"  - 환경시설 경험 업체: {len(df):,}개")
    print(f"  - 나라장터 원본 lookup: {len(raw):,}건")

    print("\n[2/4] 피처 엔지니어링 (10개)")
    df_feat = build_features(df)
    print(f"  - 생성된 피처: {CLUSTER_FEATURES}")

    print(f"\n[3/4] KMeans 클러스터링 (k={CLUSTER_K})")
    df_clustered, metrics = fit_clusters(df_feat, k=CLUSTER_K)
    print(f"  - silhouette score: {metrics['silhouette']:.3f}")
    print("  - 페르소나 분포:")
    for persona, cnt in df_clustered["페르소나"].value_counts().items():
        print(f"      {persona}: {cnt:,}개")

    df_clustered.to_csv(OUTPUT_CLUSTERS, index=False, encoding="utf-8-sig")
    print(f"  → 저장: {OUTPUT_CLUSTERS.name}")

    print("\n[4/4] 추천 데모 (3건)")
    demos = [
        ("하수처리", 500_000_000, {}),
        ("소각", 1_000_000_000, {}),
        ("바이오가스", 300_000_000, {"require_social": True}),
    ]

    all_recs = []
    for kw, budget, opts in demos:
        opt_str = f" + 옵션={opts}" if opts else ""
        print(f"\n  ▶ '{kw}' / 추정 {budget/1e8:.1f}억원{opt_str}")
        rec = recommend_suppliers(kw, budget, df_clustered, raw, top_n=5, **opts)
        if not rec.empty:
            print(rec.to_string(index=False))
            rec = rec.copy()
            rec["발주_키워드"] = kw
            rec["발주_예산"] = budget
            all_recs.append(rec)

    if all_recs:
        pd.concat(all_recs, ignore_index=True).to_csv(
            OUTPUT_RECS, index=False, encoding="utf-8-sig"
        )
        print(f"\n  → 저장: {OUTPUT_RECS.name}")

    print("\n" + "=" * 70)
    print("완료. 다음 단계: 회의 후 가중치/페르소나 규칙 조정.")
    print("=" * 70)


if __name__ == "__main__":
    main()
