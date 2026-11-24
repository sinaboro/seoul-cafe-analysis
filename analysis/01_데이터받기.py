"""
01_데이터받기.py - 서울 열린데이터광장 Open API 로 커피 업종 상권 데이터를 받아 CSV 로 저장한다

── 전체 흐름 ──
① 인증키를 읽는다 (환경 변수 SEOUL_API_KEY 또는 프로젝트 폴더의 .env 파일)
② 분기마다 추정매출·점포 데이터를 1,000줄씩 나눠 받고, 커피(CS100010) 업종만 남긴다
③ 인구 데이터(길단위·상주·직장)는 가장 최근 분기 하나만 받는다
④ data/raw 폴더에 CSV 로 저장한다 (한글이 깨지지 않게 utf-8-sig)

실행:  python analysis/01_데이터받기.py
※ 인증키는 https://data.seoul.go.kr → 로그인 → 마이페이지 → 인증키 신청 (무료, 바로 발급)
"""
import os
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent          # 프로젝트 폴더 (analysis 의 한 단계 위)
RAW = ROOT / "data" / "raw"                             # 받은 원본 데이터를 둘 곳
RAW.mkdir(parents=True, exist_ok=True)                  # 폴더가 없으면 만든다

COFFEE = "CS100010"                                     # 서비스 업종 코드: 커피-음료
QUARTERS = ["20243", "20244", "20251", "20252",         # 받을 분기 (연도 4자리 + 분기 1자리)
            "20253", "20254", "20261", "20262"]
LATEST = QUARTERS[-1]                                   # 인구 데이터는 가장 최근 분기만


def read_key():
    """인증키 읽기: 환경 변수가 있으면 그것을, 없으면 .env 파일의 SEOUL_API_KEY=… 줄을 쓴다"""
    key = os.environ.get("SEOUL_API_KEY")
    env_file = ROOT / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("SEOUL_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        raise SystemExit("인증키가 없습니다. 프로젝트 폴더에 .env 파일을 만들고 SEOUL_API_KEY=내키 를 적으세요.")
    return key


def fetch(key, service, quarter):
    """서비스 하나의 한 분기 데이터를 모두 받아 표(DataFrame)로 돌려준다 (한 번에 최대 1,000줄)"""
    rows = []                                           # 받은 줄을 모을 목록
    start = 1                                           # 몇 번째 줄부터 받을지
    while True:
        end = start + 999                               # 1,000줄씩
        url = f"http://openapi.seoul.go.kr:8088/{key}/json/{service}/{start}/{end}/{quarter}"
        data = requests.get(url, timeout=30).json()     # 요청을 보내고 JSON 으로 받기
        body = data.get(service)                        # 실제 내용은 서비스 이름 아래에 있다
        if body is None:                                # 데이터가 없거나 오류이면 멈춘다
            print("   응답:", data.get("RESULT", data))
            break
        rows.extend(body["row"])                        # 이번에 받은 줄을 모은다
        total = body["list_total_count"]                # 전체 줄 수
        if end >= total:                                # 마지막 줄까지 받았으면 끝
            break
        start = end + 1                                 # 다음 1,000줄
        time.sleep(0.2)                                 # 서버에 부담을 덜 주려고 잠깐 쉰다
    return pd.DataFrame(rows)


def main():
    key = read_key()

    # ② 분기별 추정매출·점포: 모든 업종이 함께 오므로 커피만 남긴다
    for service, name in [("VwsmAdstrdSelngW", "추정매출"), ("VwsmAdstrdStorW", "점포")]:
        parts = []
        for q in QUARTERS:
            df = fetch(key, service, q)
            coffee = df[df["SVC_INDUTY_CD"] == COFFEE]  # 커피-음료 업종만
            print(f"{name} {q}: 전체 {len(df):,}줄 중 커피 {len(coffee):,}줄")
            parts.append(coffee)
        result = pd.concat(parts, ignore_index=True)    # 분기별 표를 위아래로 붙인다
        result.to_csv(RAW / f"{name}_커피.csv", index=False, encoding="utf-8-sig")

    # ③ 인구 데이터: 업종 구분이 없으므로 최근 분기 전체를 저장
    for service, name in [("VwsmAdstrdFlpopW", "길단위인구"), ("VwsmAdstrdRepopW", "상주인구"),
                          ("VwsmAdstrdWrcPopltnW", "직장인구")]:
        df = fetch(key, service, LATEST)
        # 길단위인구·상주인구 API 는 분기 조건을 무시하고 모든 분기를 보낸다 → 받은 뒤 한 번 더 거른다
        df = df[df["STDR_YYQU_CD"].astype(str) == LATEST]
        print(f"{name} {LATEST}: {len(df):,}줄")
        df.to_csv(RAW / f"{name}.csv", index=False, encoding="utf-8-sig")

    print("저장 위치:", RAW)


if __name__ == "__main__":
    main()
