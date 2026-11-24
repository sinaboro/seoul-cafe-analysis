"""
02_데이터정리.py - 받은 원본(영문 열 이름)을 분석하기 좋은 표 두 개로 정리한다

── 전체 흐름 ──
① 원본 CSV 5개를 읽고, 쓸 열만 골라 한글 이름으로 바꾼다
② 행정동 코드 앞 5자리로 자치구 이름을 붙인다
③ 추정매출 + 점포를 (분기, 행정동) 으로 합쳐 '분기별' 표를 만든다 → 점포당 매출, 프랜차이즈 비율
④ 최근 분기에 인구 3종을 합쳐 '최근 분기' 표를 만든다 → 점포 1곳당 유동·직장·상주 인구
⑤ data/clean 폴더에 저장한다

실행:  python analysis/02_데이터정리.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
CLEAN.mkdir(parents=True, exist_ok=True)

# 행정동 코드(8자리)의 앞 5자리 = 자치구 코드
GU = {"11110": "종로구", "11140": "중구", "11170": "용산구", "11200": "성동구", "11215": "광진구",
      "11230": "동대문구", "11260": "중랑구", "11290": "성북구", "11305": "강북구", "11320": "도봉구",
      "11350": "노원구", "11380": "은평구", "11410": "서대문구", "11440": "마포구", "11470": "양천구",
      "11500": "강서구", "11530": "구로구", "11545": "금천구", "11560": "영등포구", "11590": "동작구",
      "11620": "관악구", "11650": "서초구", "11680": "강남구", "11710": "송파구", "11740": "강동구"}

# ① 쓸 열 → 한글 이름 (원본 열 이름은 API 문서의 영문 약어)
SALES_COLS = {
    "STDR_YYQU_CD": "분기", "ADSTRD_CD": "행정동코드", "ADSTRD_CD_NM": "행정동",
    "THSMON_SELNG_AMT": "매출액", "THSMON_SELNG_CO": "매출건수",
    "MDWK_SELNG_AMT": "주중매출", "WKEND_SELNG_AMT": "주말매출",
    "MON_SELNG_AMT": "월", "TUES_SELNG_AMT": "화", "WED_SELNG_AMT": "수", "THUR_SELNG_AMT": "목",
    "FRI_SELNG_AMT": "금", "SAT_SELNG_AMT": "토", "SUN_SELNG_AMT": "일",
    "TMZON_00_06_SELNG_AMT": "00~06시", "TMZON_06_11_SELNG_AMT": "06~11시", "TMZON_11_14_SELNG_AMT": "11~14시",
    "TMZON_14_17_SELNG_AMT": "14~17시", "TMZON_17_21_SELNG_AMT": "17~21시", "TMZON_21_24_SELNG_AMT": "21~24시",
    "ML_SELNG_AMT": "남성매출", "FML_SELNG_AMT": "여성매출",
    "AGRDE_10_SELNG_AMT": "10대", "AGRDE_20_SELNG_AMT": "20대", "AGRDE_30_SELNG_AMT": "30대",
    "AGRDE_40_SELNG_AMT": "40대", "AGRDE_50_SELNG_AMT": "50대", "AGRDE_60_ABOVE_SELNG_AMT": "60대이상",
}
STORE_COLS = {
    "STDR_YYQU_CD": "분기", "ADSTRD_CD": "행정동코드",
    "SIMILR_INDUTY_STOR_CO": "점포수",          # 전체 점포 = 일반 점포(STOR_CO) + 프랜차이즈(FRC_STOR_CO)
    "FRC_STOR_CO": "프랜차이즈수",
    "OPBIZ_RT": "개업률", "CLSBIZ_RT": "폐업률",   # 단위 % (그 분기에 문을 연/닫은 점포 비율)
    "OPBIZ_STOR_CO": "개업수", "CLSBIZ_STOR_CO": "폐업수",
}


def load(name, cols):
    """원본 CSV 를 읽어 필요한 열만 고르고 이름을 바꾼다. 코드 열은 글자로 읽어 앞자리 0 이 사라지지 않게 한다"""
    df = pd.read_csv(RAW / name, dtype={"STDR_YYQU_CD": str, "ADSTRD_CD": str})
    return df[list(cols)].rename(columns=cols)


def main():
    sales = load("추정매출_커피.csv", SALES_COLS)
    store = load("점포_커피.csv", STORE_COLS)

    # ② 자치구 붙이기: 행정동코드 앞 5자리를 GU 사전에서 찾는다
    sales["자치구"] = sales["행정동코드"].str[:5].map(GU)

    # ③ 분기별 표: 매출과 점포를 (분기, 행정동코드) 로 합친다. how="left" = 매출 표의 모든 줄을 남긴다
    q = sales.merge(store, on=["분기", "행정동코드"], how="left")
    # 점포가 0 인 동은 나눗셈이 무한대가 되므로 NaN(값 없음)으로 바꿔 계산에서 뺀다
    q["점포당매출"] = q["매출액"] / q["점포수"].replace(0, np.nan)
    q["프랜차이즈비율"] = q["프랜차이즈수"] / q["점포수"].replace(0, np.nan) * 100
    q["건당매출"] = q["매출액"] / q["매출건수"].replace(0, np.nan)
    q.to_csv(CLEAN / "커피_분기별.csv", index=False, encoding="utf-8-sig")

    # ④ 최근 분기 표 + 인구 3종 (모두 행정동코드로 합친다)
    latest = q["분기"].max()
    last = q[q["분기"] == latest].copy()
    flpop = pd.read_csv(RAW / "길단위인구.csv", dtype={"ADSTRD_CD": str})[["ADSTRD_CD", "TOT_FLPOP_CO"]]
    repop = pd.read_csv(RAW / "상주인구.csv", dtype={"ADSTRD_CD": str})[["ADSTRD_CD", "TOT_REPOP_CO"]]
    wrc = pd.read_csv(RAW / "직장인구.csv", dtype={"ADSTRD_CD": str})[["ADSTRD_CD", "TOT_WRC_POPLTN_CO"]]
    for df, col, new in [(flpop, "TOT_FLPOP_CO", "유동인구"), (repop, "TOT_REPOP_CO", "상주인구"),
                         (wrc, "TOT_WRC_POPLTN_CO", "직장인구")]:
        df = df.rename(columns={"ADSTRD_CD": "행정동코드", col: new})
        last = last.merge(df, on="행정동코드", how="left")
    # 유동인구는 분기 합계 → 하루 평균으로 (2분기 = 4~6월 91일)
    last["유동인구_일평균"] = last["유동인구"] / 91
    stores = last["점포수"].replace(0, np.nan)
    last["점포당_유동인구"] = last["유동인구_일평균"] / stores
    last["점포당_직장인구"] = last["직장인구"] / stores
    last["점포당_상주인구"] = last["상주인구"] / stores
    last.to_csv(CLEAN / "커피_최근분기.csv", index=False, encoding="utf-8-sig")

    print(f"분기별 표: {len(q):,}줄 ({q['분기'].nunique()}개 분기, 행정동 {q['행정동코드'].nunique()}곳)")
    print(f"최근 분기({latest}) 표: {len(last):,}줄")
    print("자치구가 비어 있는 줄:", int(q["자치구"].isna().sum()))
    empty = last.isna().sum()                          # 열마다 빈 값(NaN) 개수
    print("빈 값이 있는 열:", empty[empty > 0].to_dict())  # 0 보다 큰 열만 보여 준다


if __name__ == "__main__":
    main()
