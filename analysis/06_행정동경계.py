"""
06_행정동경계.py - 지도에 색을 칠할 '서울 행정동 경계선' 파일(GeoJSON)을 준비한다

── 전체 흐름 ──
① 전국 행정동 경계 GeoJSON(약 35MB)을 GitHub 저장소 vuski/admdongkor 에서 받는다
② 서울(행정동 코드가 11 로 시작)만 남긴다
③ 좌표를 소수 5자리(약 1m)로 줄여 파일 크기를 줄인다 → 브라우저가 빨리 받는다
④ 우리 상권 데이터와 같은 8자리 행정동코드를 붙여 data/clean/서울_행정동.geojson 으로 저장한다

GeoJSON 이란?  지도 위의 모양(점·선·면)과 그 이름표를 JSON 글자로 적은 파일.
               { "type": "FeatureCollection", "features": [ {모양 하나}, {모양 하나}, ... ] }

실행:  python analysis/06_행정동경계.py
출처 표기(꼭 화면에 남길 것): 통계청 SGIS 행정동 경계(공공누리 1유형), 가공 vuski/admdongkor (CC BY 4.0)
"""
import json
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean"
# 어느 날짜 기준 경계를 쓸까?  서울시 상권분석 데이터는 2021년 초의 행정동 구분을 지금도 그대로 쓴다.
# (그 뒤 상일동 → 상일1·2동, 일원2동 → 개포3동 처럼 바뀐 동이 있다)
# 최신 경계(ver2026...)를 쓰면 3개 동이 짝을 못 찾아 색이 비므로, 데이터와 같은 2021년 1월 경계를 쓴다.
VERSION = "ver20210101"
URL = ("https://raw.githubusercontent.com/vuski/admdongkor/master/"
       f"{VERSION}/HangJeongDong_{VERSION}.geojson")


def round_coords(coords):
    """[[경도, 위도], ...] 처럼 겹겹이 든 목록을 끝까지 따라가며 숫자를 소수 5자리로 줄인다"""
    if isinstance(coords[0], (int, float)):              # 맨 안쪽: [경도, 위도] 한 점
        return [round(coords[0], 5), round(coords[1], 5)]
    return [round_coords(c) for c in coords]             # 아직 목록이면 한 겹 더 들어간다


def main():
    # ① 전국 파일 받기
    print("전국 행정동 경계 받는 중 (약 35MB)...")
    geo = requests.get(URL, timeout=180).json()
    print(f"전국 행정동 {len(geo['features']):,}개")

    # ② 서울만.  properties 예: {"adm_nm": "서울특별시 종로구 사직동", "adm_cd2": "1111053000", ...}
    seoul = [f for f in geo["features"] if f["properties"]["adm_cd2"].startswith("11")]

    # ④ 우리 데이터의 행정동코드(8자리)와 맞추기: adm_cd2(10자리)의 앞 8자리
    for f in seoul:
        p = f["properties"]
        names = p["adm_nm"].split()                       # ["서울특별시", "종로구", "사직동"]
        f["properties"] = {"행정동코드": p["adm_cd2"][:8], "자치구": names[1], "행정동": names[2]}
        f["geometry"]["coordinates"] = round_coords(f["geometry"]["coordinates"])   # ③

    out = {"type": "FeatureCollection", "features": seoul}
    path = CLEAN / "서울_행정동.geojson"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"저장: {path.relative_to(ROOT)} (행정동 {len(seoul)}개, {path.stat().st_size / 1e6:.1f}MB)")

    # 확인: 상권 데이터의 행정동코드가 경계 파일에 모두 있는가?
    last = pd.read_csv(CLEAN / "커피_최근분기.csv", dtype={"행정동코드": str})
    codes = {f["properties"]["행정동코드"] for f in seoul}
    missing = last[~last["행정동코드"].isin(codes)]
    print(f"상권 데이터 행정동 {len(last)}개 중 경계 파일에 없는 곳: {len(missing)}개")
    if len(missing):
        print(missing[["자치구", "행정동", "행정동코드"]].to_string(index=False))


if __name__ == "__main__":
    main()
