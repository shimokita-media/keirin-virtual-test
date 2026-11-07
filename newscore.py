"""新しい点数方式（2026-11-08〜、通知に表示するだけ。買い目の選び方は変えない）。
各1点：同じライン／単騎を含まない／3番手以降を含む×風4m未満／地元を含む同じライン／先頭を含む×風6m以上／欠場のあったレースの同じライン。
5〜11月の最終オッズでは、ワイド6〜10倍・割安度0.85以上のうち3点以上が142%（締切前で選んだ場合の確認はこれから）。
風は Open-Meteo（無料の公開天気データ）の、競輪場のある市の1時間ごとの風速。取れないときは風の項目を数えない。"""
import json
import re
import time
import urllib.request

V = {"函館": (41.77, 140.73), "青森": (40.82, 140.74), "いわき平": (37.05, 140.89), "弥彦": (37.69, 138.82), "前橋": (36.39, 139.06), "取手": (35.91, 140.05),
     "宇都宮": (36.56, 139.88), "大宮": (35.92, 139.63), "西武園": (35.77, 139.45), "京王閣": (35.65, 139.55), "立川": (35.71, 139.41), "松戸": (35.79, 139.90),
     "千葉": (35.61, 140.12), "川崎": (35.53, 139.70), "平塚": (35.33, 139.35), "小田原": (35.26, 139.15), "伊東": (34.97, 139.10), "静岡": (34.98, 138.38),
     "名古屋": (35.17, 136.88), "岐阜": (35.42, 136.76), "大垣": (35.36, 136.62), "豊橋": (34.77, 137.39), "富山": (36.70, 137.21), "松阪": (34.58, 136.53),
     "四日市": (34.97, 136.62), "福井": (36.06, 136.22), "奈良": (34.68, 135.80), "和歌山": (34.23, 135.17), "岸和田": (34.46, 135.37), "向日町": (34.95, 135.70),
     "玉野": (34.49, 133.95), "広島": (34.39, 132.46), "防府": (34.05, 131.56), "小松島": (34.00, 134.59), "高松": (34.34, 134.05), "高知": (33.56, 133.53),
     "松山": (33.84, 132.77), "小倉": (33.88, 130.88), "久留米": (33.32, 130.51), "武雄": (33.19, 130.02), "佐世保": (33.18, 129.72), "別府": (33.28, 131.49), "熊本": (32.79, 130.74)}
VP = dict(函館="北海道", 青森="青森", いわき平="福島", 弥彦="新潟", 前橋="群馬", 取手="茨城", 宇都宮="栃木", 大宮="埼玉", 西武園="埼玉", 京王閣="東京", 立川="東京", 松戸="千葉", 千葉="千葉", 川崎="神奈川", 平塚="神奈川", 小田原="神奈川", 伊東="静岡", 静岡="静岡", 名古屋="愛知", 岐阜="岐阜", 大垣="岐阜", 豊橋="愛知", 富山="富山", 松阪="三重", 四日市="三重", 福井="福井", 奈良="奈良", 和歌山="和歌山", 岸和田="大阪", 向日町="京都", 玉野="岡山", 広島="広島", 防府="山口", 小松島="徳島", 高松="香川", 高知="高知", 松山="愛媛", 小倉="福岡", 久留米="福岡", 武雄="佐賀", 佐世保="長崎", 別府="大分", 熊本="熊本")

_cache = {}


def wind(venue, start_ts):
    """そのレースの発走時刻の風速（m/秒）。取れなければ None"""
    if venue not in V:
        return None
    hour = time.strftime("%Y-%m-%dT%H", time.gmtime(start_ts + 9 * 3600))  # 日本時間
    key = (venue, hour[:10])
    if key not in _cache or time.time() - _cache[key][0] > 3600:
        la, lo = V[venue]
        u = (f"https://api.open-meteo.com/v1/forecast?latitude={la}&longitude={lo}&past_days=1&forecast_days=2"
             "&hourly=wind_speed_10m&wind_speed_unit=ms&timezone=Asia%2FTokyo")
        try:
            h = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "keirin-research"}), timeout=10))["hourly"]
            _cache[key] = (time.time(), dict(zip(h["time"], h["wind_speed_10m"])))
        except Exception:
            _cache[key] = (time.time() - 3000, {})  # 失敗したら10分後にもう一度
    return _cache[key][1].get(hour + ":00")


def score(con, row, combo, n_picks=None):
    """(点, 当てはまった項目のリスト, 風速)"""
    lines = [[x for e in l["entries"] for x in e["numbers"]] for l in json.loads(row["line_json"] or "[]")]
    lid = {x: i for i, l in enumerate(lines) for x in l}
    pos = {x: k for l in lines for k, x in enumerate(l)}
    ls = {x: len(l) for l in lines for x in l}
    ent = {n: (p, c or "", ab) for n, p, c, ab in con.execute(
        "SELECT number, prefecture, comment, absent FROM entries WHERE race_id=?", (row["race_id"],))}
    absent = any(v[2] for v in ent.values())
    w = wind(row["venue"], row["start_at"] or row["close_at"])
    a, b = map(int, combo.split("-"))
    same = a in lid and lid.get(a) == lid.get(b)
    single = any(ls.get(n, 1) == 1 or re.search("単騎|１人|一人|1人", (ent.get(n) or ("", "", 0))[1]) for n in (a, b))
    hits = []
    if same: hits.append("同じライン")
    if not single: hits.append("単騎なし")
    if w is not None and w < 4 and any(pos.get(n, 0) >= 2 for n in (a, b)): hits.append("3番手×弱い風")
    if same and any((ent.get(n) or ("",))[0] == VP.get(row["venue"]) for n in (a, b)): hits.append("地元")
    if w is not None and w >= 6 and any(pos.get(n, -1) == 0 and ls.get(n, 1) >= 2 for n in (a, b)): hits.append("先頭×強い風")
    if same and absent: hits.append("欠場あり")
    return len(hits), hits, w
