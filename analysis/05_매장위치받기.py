"""
05_매장위치받기.py - 서울 커피숍 한 곳 한 곳의 위치(위도·경도)를 받아 지도용 CSV 로 저장한다

── 전체 흐름 ──
① 01 과 같은 인증키로 「서울시 휴게음식점 인허가 정보」(LOCALDATA_072405) 를 1,000줄씩 모두 받는다
   (이 API 는 업태로 거르는 기능이 없어서 커피숍이 아닌 곳까지 전부 온다 → 받은 뒤 pandas 로 거른다)
② 업태가 '커피숍' 이고 지금 '영업' 중인 곳만 남긴다 (폐업한 가게가 훨씬 많다)
③ 좌표 X, Y 는 우리나라 옛 좌표계(EPSG:5174, 단위 m)라서 지도가 쓰는 위도·경도(EPSG:4326)로 바꾼다
④ 주소에서 자치구 이름을 뽑고, 지도에 필요한 열만 data/clean/커피숍_위치.csv 로 저장한다

실행:  python analysis/05_매장위치받기.py      (약 150번 요청 → 2~4분 걸린다)
필요:  pip install pyproj
"""
import time
from pathlib import Path

import pandas as pd
import requests
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
SERVICE = "LOCALDATA_072405"                            # 서울시 휴게음식점 인허가 정보

# 01 에서 만든 인증키 읽기 함수를 그대로 다시 쓴다 (파일 이름이 숫자로 시작해서 import 대신 이렇게 불러온다)
import importlib.util                                   # noqa: E402
_spec = importlib.util.spec_from_file_location("step01", ROOT / "analysis" / "01_데이터받기.py")
_step01 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_step01)
read_key = _step01.read_key


def fetch_all(key):
    """인허가 정보 전체를 1,000줄씩 받아 표 하나로 돌려준다"""
    rows, start = [], 1
    while True:
        end = start + 999
        url = f"http://openapi.seoul.go.kr:8088/{key}/json/{SERVICE}/{start}/{end}/"
        for attempt in range(3):                        # 가끔 응답이 늦으면 두 번 더 시도한다
            try:
                data = requests.get(url, timeout=60).json()
                break
            except (requests.RequestException, ValueError):
                print("   다시 시도", attempt + 1)
                time.sleep(2)
        else:
            raise SystemExit(f"{start}~{end} 줄을 받지 못했습니다. 잠시 뒤 다시 실행하세요.")
        body = data.get(SERVICE)
        if body is None:                                # 인증키 오류 등
            raise SystemExit(f"응답 오류: {data.get('RESULT', data)}")
        rows.extend(body["row"])
        total = body["list_total_count"]
        if start == 1 or end % 20000 == 0 or end >= total:
            print(f"   {min(end, total):,} / {total:,} 줄")
        if end >= total:
            break
        start = end + 1
        time.sleep(0.2)
    return pd.DataFrame(rows)


def main():
    key = read_key()

    # ① 전체 받기 (약 15만 줄)
    print("휴게음식점 인허가 정보 받는 중...")
    df = fetch_all(key)

    # ② 커피숍 + 영업 중만 남기기.  TRDSTATENM(영업상태명): 영업/정상, 휴업, 폐업 ...
    df["UPTAENM"] = df["UPTAENM"].str.strip()
    cafe = df[(df["UPTAENM"] == "커피숍") & (df["TRDSTATENM"].str.contains("영업"))].copy()
    print(f"전체 {len(df):,}곳 중 영업 중인 커피숍 {len(cafe):,}곳")
    cafe.to_csv(RAW / "커피숍_인허가.csv", index=False, encoding="utf-8-sig")   # 원본도 남겨 둔다

    # ③ 좌표 바꾸기. 값 뒤에 공백이 붙어 오므로 숫자로 바꾸고, 좌표가 빈 가게는 뺀다
    cafe["X"] = pd.to_numeric(cafe["X"].str.strip(), errors="coerce")
    cafe["Y"] = pd.to_numeric(cafe["Y"].str.strip(), errors="coerce")
    print(f"좌표가 비어 있어 뺀 곳: {cafe['X'].isna().sum()}곳")
    cafe = cafe.dropna(subset=["X", "Y"])
    # always_xy=True : (x, y) = (동쪽 방향, 북쪽 방향) 순서로 주고받는다 → 결과는 (경도, 위도)
    to_wgs84 = Transformer.from_crs("EPSG:5174", "EPSG:4326", always_xy=True)
    cafe["경도"], cafe["위도"] = to_wgs84.transform(cafe["X"].values, cafe["Y"].values)
    # 서울 바깥으로 튄 좌표(잘못 입력된 값)는 뺀다. 서울은 대략 위도 37.4~37.7, 경도 126.7~127.2
    inside = cafe["위도"].between(37.40, 37.72) & cafe["경도"].between(126.76, 127.19)
    print(f"서울 밖 좌표라 뺀 곳: {(~inside).sum()}곳")
    cafe = cafe[inside]

    # ④ 도로명 주소가 있으면 그것을, 없으면 지번 주소를 쓴다. 자치구는 주소의 두 번째 낱말
    cafe["주소"] = cafe["RDNWHLADDR"].where(cafe["RDNWHLADDR"].str.strip() != "", cafe["SITEWHLADDR"])
    cafe["자치구"] = cafe["주소"].str.split().str[1]
    cafe["개업일"] = cafe["APVPERMYMD"].str.strip()
    out = cafe.rename(columns={"BPLCNM": "상호"})[["상호", "자치구", "주소", "개업일", "위도", "경도"]]
    out = out[out["자치구"].str.endswith("구", na=False)]                     # 주소가 이상한 줄 빼기
    out["위도"], out["경도"] = out["위도"].round(6), out["경도"].round(6)      # 소수 6자리 ≈ 10cm
    out.to_csv(CLEAN / "커피숍_위치.csv", index=False, encoding="utf-8-sig")
    print(f"저장: data/clean/커피숍_위치.csv ({len(out):,}곳)")
    print(out["자치구"].value_counts().head(5).to_string())


if __name__ == "__main__":
    main()
