"""競輪場ごとの1時間ごとの気温（Open-Meteo の過去データ API、2023/11/1〜2026/11/5）を out/wx_temp/{場}.json に保存。取ってあれば飛ばす。
使い方: python -X utf8 research/wx_temp_get.py"""
import json, time, urllib.request, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from newscore import V
D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out", "wx_temp"); os.makedirs(D, exist_ok=True)
for v, (la, lo) in V.items():
    f = os.path.join(D, f"{v}.json")
    if os.path.exists(f): continue
    u = (f"https://archive-api.open-meteo.com/v1/archive?latitude={la}&longitude={lo}&start_date=2023-11-01&end_date=2026-11-05"
         "&hourly=temperature_2m,precipitation&timezone=Asia%2FTokyo")
    h = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "keirin-research"}), timeout=60))["hourly"]
    json.dump(h, open(f, "w", encoding="utf-8")); time.sleep(2)
print(len(os.listdir(D)))
