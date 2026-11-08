import json, time, urllib.request, sys, os
exec(open("coords.py", encoding="utf-8").read())
for v, (la, lo) in V.items():
    f = f"wx4/{v}.json"
    if os.path.exists(f): continue
    u = (f"https://archive-api.open-meteo.com/v1/archive?latitude={la}&longitude={lo}&start_date=2023-11-01&end_date=2026-01-31"
         "&hourly=wind_speed_10m&wind_speed_unit=ms&timezone=Asia%2FTokyo")
    h = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "keirin-research"}), timeout=30))["hourly"]
    json.dump(h, open(f, "w", encoding="utf-8")); time.sleep(1.5)
print(len(os.listdir("wx4")))
