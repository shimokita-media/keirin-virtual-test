"""競輪 市場の歪み検出システム（仮想購入のみ・実投票なし）

データソース
  - WINTICKET レースページ SSR (/keirin/{slug}/racecard/...)  robots.txt 許可パス
      開催一覧・出走表・選手情報・並び予想・コメント・組番別オッズ(+更新時刻)・確定着順/的中組番
  - netkeirin 公開JSON (keirin.netkeiba.com/api/race/ class=AplRaceOdds)  robots.txt 全許可
      組番別オッズの照合用
  - オッズパークは robots.txt で ClaudeBot を拒否しているため不使用
"""
import datetime as dt
import hashlib
import itertools
import json
import os
import sqlite3
import time
from zoneinfo import ZoneInfo

import requests

JST = ZoneInfo("Asia/Tokyo")
BASE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (personal research; low-rate)"}
REQ_INTERVAL = 2.0  # 秒。各サイトへの最小リクエスト間隔
TAKEOUT_RETURN = 0.75  # 競輪の払戻率（全券種）

GRADE = {1: "FII", 2: "FI", 3: "GIII", 4: "GII", 5: "GI", 6: "GP"}  # netkeirin表記と照合済み(FI/FII)
GRADE_PRIORITY = {"GP": 0, "GI": 1, "GII": 2, "GIII": 3, "FI": 4, "FII": 5}
# WINTICKET type番号 / netkeirin list番号 -> 券種
WT_TYPES = {"trifecta": "3連単", "trio": "3連複", "exacta": "2車単", "quinella": "2車複", "quinellaPlace": "ワイド"}
WT_TYPE_NO = {2: "3連単", 3: "3連複", 4: "2車単", 5: "2車複", 6: "ワイド"}
NK_TYPES = {"list_9": "3連単", "list_8": "3連複", "list_6": "2車単", "list_5": "2車複", "list_7": "ワイド"}
BET_TYPES = ["3連単", "3連複", "2車単", "2車複", "ワイド"]

_last_req = {}


def now():
    return dt.datetime.now(JST)


def ts(t):
    return dt.datetime.fromtimestamp(t, JST).strftime("%Y-%m-%d %H:%M:%S") if t else ""


def _get(host, fn):
    wait = REQ_INTERVAL - (time.time() - _last_req.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    try:
        return fn()
    finally:
        _last_req[host] = time.time()


# ---------------------------------------------------------------- DB
def db():
    con = sqlite3.connect(os.path.join(BASE, "keirin.sqlite"), timeout=60)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS races(race_id TEXT PRIMARY KEY, date TEXT, venue_id TEXT, venue TEXT, slug TEXT,
      cup_id TEXT, cup_name TEXT, grade TEXT, day_index INT, race_no INT, class TEXT, race_type TEXT,
      close_at INT, start_at INT, status INT, entries_number INT, line_type TEXT, line_json TEXT,
      advancement TEXT, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS entries(race_id TEXT, number INT, bracket INT, player_id TEXT, name TEXT,
      prefecture TEXT, term INT, age INT, class INT, grp INT, style TEXT, gear REAL, race_point REAL,
      comment TEXT, prediction_mark INT, first_rate REAL, second_rate REAL, third_rate REAL,
      n_front INT, n_stalker INT, n_closer INT, n_marker INT, recent_orders TEXT, absent INT,
      fetched_at TEXT, PRIMARY KEY(race_id, number));
    CREATE TABLE IF NOT EXISTS odds(race_id TEXT, source TEXT, bet_type TEXT, combo TEXT, odds REAL,
      odds_max REAL, popularity INT, source_updated_at TEXT, fetched_at TEXT, phase TEXT,
      PRIMARY KEY(race_id, source, fetched_at, bet_type, combo));
    CREATE TABLE IF NOT EXISTS fetch_log(at TEXT, source TEXT, url TEXT, race_id TEXT, ok INT, n INT, note TEXT);
    CREATE TABLE IF NOT EXISTS predictions(pred_id INTEGER PRIMARY KEY AUTOINCREMENT, race_id TEXT, phase TEXT,
      created_at TEXT, close_at TEXT, minutes_to_close REAL, bet_type TEXT, combo TEXT, stake INT,
      ref_odds REAL, ref_source TEXT, ref_odds_fetched_at TEXT, ref_source_updated_at TEXT,
      model_prob REAL, ev_a10 REAL, ev_a115 REAL, bet_rating TEXT, race_rating TEXT, reason TEXT, sha TEXT);
    CREATE TRIGGER IF NOT EXISTS pred_no_update BEFORE UPDATE ON predictions
      BEGIN SELECT RAISE(ABORT, 'predictions is append-only'); END;
    CREATE TRIGGER IF NOT EXISTS pred_no_delete BEFORE DELETE ON predictions
      BEGIN SELECT RAISE(ABORT, 'predictions is append-only'); END;
    CREATE TABLE IF NOT EXISTS race_weather(race_id TEXT PRIMARY KEY, weather INT, temperature REAL, wind_speed REAL,
      wind_direction INT, precipitation REAL, target_at INT, race_weather TEXT, race_wind REAL, fetched_at TEXT);
    -- 2026-11-10〜 前検日インタビュー（WINTICKET。1つの開催で1人1回）と、netkeirin の出走表の選手コメント
    CREATE TABLE IF NOT EXISTS interviews(cup_id TEXT, player_id TEXT, kind TEXT, race_id TEXT, schedule_id TEXT,
      qa_json TEXT, interviewer_type INT, interview_type INT, list_created_at INT, list_updated_at INT, fetched_at TEXT,
      PRIMARY KEY(cup_id, player_id, kind));
    CREATE TABLE IF NOT EXISTS rider_comments(race_id TEXT, number INT, player_id TEXT, source TEXT, comment TEXT,
      fetched_at TEXT, PRIMARY KEY(race_id, number, source));
    -- 2026-11-10〜 レース後インタビュー（WINTICKET の結果ページ。1レース1人1行）
    CREATE TABLE IF NOT EXISTS result_interviews(race_id TEXT, player_id TEXT, cup_id TEXT, schedule_id TEXT, qa_json TEXT,
      interviewer_type INT, interview_type INT, fetched_at TEXT, PRIMARY KEY(race_id, player_id));
    -- 2026-11-10〜 選手の条件別の成績（WINTICKET の出走表 records。ライン内の位置別・バンク別・時間帯別・天気別・レースの種類別・戦法の成功率など）。1レース1人1行、最初に取れたもの
    CREATE TABLE IF NOT EXISTS rider_stats(race_id TEXT, number INT, player_id TEXT, stats_json TEXT, fetched_at TEXT,
      PRIMARY KEY(race_id, number));
    CREATE TABLE IF NOT EXISTS results(race_id TEXT, rank INT, number INT, player_id TEXT, factor TEXT,
      margin TEXT, fetched_at TEXT, PRIMARY KEY(race_id, rank, number));
    CREATE TABLE IF NOT EXISTS payouts(race_id TEXT, bet_type TEXT, combo TEXT, payout INT, popularity INT,
      fetched_at TEXT, PRIMARY KEY(race_id, bet_type, combo));
    """)
    # 2026-11-07〜 S（スタート取り）・B（バック）の回数も記録する（出走表に載っている数字）
    cols = {r[1] for r in con.execute("PRAGMA table_info(entries)")}
    for c in ("n_standing", "n_back"):
        if c not in cols:
            con.execute(f"ALTER TABLE entries ADD COLUMN {c} INT")
    # 上がりタイム（今の開催＋前の開催の各レース。0.0=記録なしは除く）の平均・最速・本数
    for c, t in (("agari_avg", "REAL"), ("agari_best", "REAL"), ("agari_n", "INT")):
        if c not in cols:
            con.execute(f"ALTER TABLE entries ADD COLUMN {c} {t}")
    return con


def agari(rc):
    """出走表の記録から上がりタイムをまとめる。(平均, 最速, 本数)。本数0なら (None, None, 0)"""
    ts_ = []
    for x in (rc.get("currentCupResults") or []) + (rc.get("previousCupResults") or []):
        try:
            v = float(x.get("finalHalfRecord") or 0)
        except ValueError:
            continue
        if v > 0:
            ts_.append(v)
    return (round(sum(ts_) / len(ts_), 2), min(ts_), len(ts_)) if ts_ else (None, None, 0)


def log(con, source, url, race_id, ok, n=0, note=""):
    con.execute("INSERT INTO fetch_log VALUES(?,?,?,?,?,?,?)",
                (now().isoformat(timespec="seconds"), source, url, race_id, int(ok), n, note[:300]))
    con.commit()


# ---------------------------------------------------------------- WINTICKET
def wt_state(url):
    r = _get("wt", lambda: requests.get(url, headers=UA, timeout=20))
    r.raise_for_status()
    h = r.text
    i = h.index("window.__PRELOADED_STATE__")
    i = h.index("{", i)
    d, _ = json.JSONDecoder().raw_decode(h[i:])
    return {q["queryKey"][1]: q["state"]["data"] for q in d["tanStackQuery"]["queries"]}, d.get("unixnow")


def fetch_daily(con, date=None):
    """開催一覧（全国）。WINTICKET racecard トップ。"""
    url = "https://www.winticket.jp/keirin/racecard/"
    try:
        q, _ = wt_state(url)
        dd = q["FETCH_KEIRIN_DAILY_RACE"]
    except Exception as e:  # noqa
        log(con, "winticket", url, "", 0, 0, repr(e))
        raise
    venues = {v["id"]: v for v in q["FETCH_KEIRIN_VENUE_LIST"]["venues"]}
    cups = {c["id"]: c for c in dd["cups"]}
    sch = {s["id"]: s for s in dd["schedules"]}
    t = now().isoformat(timespec="seconds")
    for r in dd["races"]:
        s = sch[r["scheduleId"]]
        c = cups[s["cupId"]]
        v = venues[c["venueId"]]
        con.execute("""INSERT INTO races(race_id,date,venue_id,venue,slug,cup_id,cup_name,grade,day_index,race_no,
            class,race_type,close_at,start_at,status,entries_number,advancement,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(race_id) DO UPDATE SET status=excluded.status, close_at=excluded.close_at,
            start_at=excluded.start_at, entries_number=excluded.entries_number, updated_at=excluded.updated_at""",
                    (r["id"], s["date"], c["venueId"], v["name"], v["slug"], c["id"], c["name"],
                     GRADE.get(c["grade"], str(c["grade"])), s["index"], r["number"], r["class"], r["raceType"],
                     r["closeAt"], r["startAt"], r["status"], r["entriesNumber"],
                     r.get("advancementConditionText", ""), t))
    con.commit()
    log(con, "winticket", url, "", 1, len(dd["races"]), f"cups={len(cups)}")
    return len(cups), len(dd["races"])


def race_url(row):
    return f"https://www.winticket.jp/keirin/{row['slug']}/racecard/{row['cup_id']}/{row['day_index']}/{row['race_no']}"


def save_interviews(con, q, rid, t, cup_id=None):
    """前検日インタビュー（レースページに載っている、そのレースの選手の分）を interviews に保存する。
    1つの開催で1人1行（cup_id・player_id）。中身（threads＝質問と答え）のない選手は保存しない。
    同じ中身なら書き換えない（fetched_at＝最初に取れた時刻が残る）。WINTICKET に残っているのは 2025年末〜2026年初めごろ以降の開催だけ。
    戻り値: 新しく保存・更新した人数"""
    iv = q.get("FETCH_KEIRIN_INSPECTION_DAY_INTERVIEW_LIST") or {}
    n = 0
    for it in iv.get("interviews") or []:
        th = it.get("threads") or []
        if not th or not it.get("playerId"):
            continue
        cur = con.execute("""INSERT INTO interviews VALUES(?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(cup_id, player_id, kind) DO UPDATE SET qa_json=excluded.qa_json,
              interviewer_type=excluded.interviewer_type, interview_type=excluded.interview_type,
              list_updated_at=excluded.list_updated_at
            WHERE excluded.qa_json != interviews.qa_json""",
                          (iv.get("cupId") or cup_id, it["playerId"], "前検", rid, iv.get("scheduleId"),
                           json.dumps(th, ensure_ascii=False), it.get("interviewerType"), it.get("interviewType"),
                           iv.get("createdAt"), iv.get("updatedAt"), t))
        n += max(cur.rowcount, 0)
    return n


STAT_KEYS = ("raceTypeQualifyingRound", "raceTypeSemifinal", "raceTypeFinal", "raceTypeLoserRound", "raceTypeSpecial",
             "trackDistance333", "trackDistance400", "trackDistance500", "lineSingleHorseman", "linePositionFirst",
             "linePositionSecond", "linePositionThird", "lineCompete", "weatherSunny", "weatherCloudy", "weatherRainy",
             "weatherSnowy", "hourTypeNormal", "hourTypeMorning", "hourTypeNight", "hourTypeMidnight", "hourTypeSummertime",
             "exSpurt", "exThrust", "exLeftBehind", "exSplitLine", "exSnatch", "exCompete", "first", "second", "third",
             "others", "hasHome", "home", "hasModifiedGearRatio", "modifiedGearRatio", "previousCupId")


def save_rider_stats(con, rd, rid, t):
    """出走表の records にある選手の条件別の成績（ライン内の位置別・バンク別など）を rider_stats に保存する（最初に取れたものを残す）。
    戻り値: 新しく保存した人数"""
    num = {e["playerId"]: e["number"] for e in rd.get("entries") or []}
    n = 0
    for rc in rd.get("records") or []:
        pid = rc.get("playerId")
        if pid not in num:
            continue
        st = {}
        for k in STAT_KEYS:  # 割合（Percentage）は回数から計算できるので省く：条件別は [1着,2着,3着,着外]、戦法は [回数,成功]
            v = rc.get(k)
            if isinstance(v, dict) and "others" in v:
                st[k] = [v.get("first"), v.get("second"), v.get("third"), v.get("others")]
            elif isinstance(v, dict) and "succeeded" in v:
                st[k] = [v.get("total"), v.get("succeeded")]
            elif v is not None:
                st[k] = v
        cur = con.execute("INSERT OR IGNORE INTO rider_stats VALUES(?,?,?,?,?)",
                          (rid, num[pid], pid, json.dumps(st, ensure_ascii=False, separators=(",", ":")), t))
        n += max(cur.rowcount, 0)
    return n


def result_url(row):
    """レースの結果ページの「レース後コメント」の表示（ふつうのページ。robots.txt で禁止されているのは /keirin/cups/ だけ）"""
    return (f"https://www.winticket.jp/keirin/{row['slug']}/raceresult/{row['cup_id']}/{row['day_index']}/{row['race_no']}"
            "?type=race_result_interview")


def save_result_interviews(con, q, rid, t):
    """レース後インタビュー（結果ページのデータ FETCH_KEIRIN_RACE_RESULT_INTERVIEW_LIST）を result_interviews に保存する。
    1レース1人1行。同じ中身なら書き換えない。戻り値: (中身のある人数, 新しく保存・更新した人数)"""
    iv = q.get("FETCH_KEIRIN_RACE_RESULT_INTERVIEW_LIST") or {}
    k = n = 0
    for it in iv.get("interviews") or []:
        th = it.get("threads") or []
        if not th or not it.get("playerId"):
            continue
        k += 1
        cur = con.execute("""INSERT INTO result_interviews VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(race_id, player_id) DO UPDATE SET qa_json=excluded.qa_json,
              interviewer_type=excluded.interviewer_type, interview_type=excluded.interview_type
            WHERE excluded.qa_json != result_interviews.qa_json""",
                          (rid, it["playerId"], iv.get("cupId"), iv.get("scheduleId"), json.dumps(th, ensure_ascii=False),
                           it.get("interviewerType"), it.get("interviewType"), t))
        n += max(cur.rowcount, 0)
    return k, n


def fetch_result_interviews(con, row):
    """レース後インタビューを取って保存する（2026-11-10 追加、ユーザー依頼）。結果ページ（result_url）のデータに本文が入っている。
    オッズ・出走表などは書かない。WINTICKET に残っているのは 2025/12 ごろ以降。F1・F2 の最終日は取材対象外（空）。
    戻り値: (中身のある人数, 新しく保存・更新した人数)。取得失敗は None"""
    url = result_url(row)
    rid = row["race_id"]
    try:
        q, _ = wt_state(url)
    except Exception as e:
        log(con, "winticket", url, rid, 0, 0, f"result_interviews {e!r}")
        return None
    t = now().isoformat(timespec="seconds")
    k, n = save_result_interviews(con, q, rid, t)
    con.commit()
    log(con, "winticket", url, rid, 1, n, f"result_interviews {k}")
    return k, n


def fetch_race(con, row, phase=""):
    """出走表・並び・オッズ・結果を1リクエストで取得。戻り値: (race_data, odds_dict, odds_meta)"""
    url = race_url(row)
    rid = row["race_id"]
    try:
        q, unixnow = wt_state(url)
        rd = q["FETCH_KEIRIN_RACE"]
        od = q.get("FETCH_KEIRIN_RACE_ODDS") or rd
    except Exception as e:
        log(con, "winticket", url, rid, 0, 0, repr(e))
        return None, None, None
    t = now().isoformat(timespec="seconds")
    # 出走表
    players = {p["id"]: p for p in rd["players"]}
    recs = {r["playerId"]: r for r in rd["records"]}
    for e in rd["entries"]:
        p = players.get(e["playerId"], {})
        rc = recs.get(e["playerId"], {})
        recent = [x["order"] for c in rc.get("latestCupResults", []) for x in c.get("raceResults", [])]
        con.execute("""INSERT OR REPLACE INTO entries(race_id,number,bracket,player_id,name,prefecture,term,age,class,grp,
            style,gear,race_point,comment,prediction_mark,first_rate,second_rate,third_rate,n_front,n_stalker,n_closer,
            n_marker,recent_orders,absent,fetched_at,n_standing,n_back,agari_avg,agari_best,agari_n)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (rid, e["number"], e["bracketNumber"], e["playerId"], p.get("name"), p.get("prefecture"),
                     p.get("term"), p.get("age"), p.get("class"), p.get("group"), rc.get("style"),
                     rc.get("gearRatio"), rc.get("racePoint"), rc.get("comment"), rc.get("predictionMark"),
                     rc.get("firstRate"), rc.get("secondRate"), rc.get("thirdRate"), rc.get("frontRunner"),
                     rc.get("stalker"), rc.get("deepCloser"), rc.get("marker"), json.dumps(recent),
                     int(e["absent"]), t, rc.get("standing"), rc.get("back"), *agari(rc)))
    lp = rd.get("linePrediction") or {}
    con.execute("UPDATE races SET line_type=?, line_json=?, status=?, updated_at=? WHERE race_id=?",
                (lp.get("lineType"), json.dumps(lp.get("lines", []), ensure_ascii=False),
                 rd["race"]["status"], t, rid))
    # 天気（2026-11-09 追加。保存に失敗しても本体の取り込みは止めない）
    try:
        w = q.get("FETCH_KEIRIN_RACE_WEATHER") or {}
        rr = rd.get("race") or {}
        num = lambda v: float(v) if v not in (None, "") else None
        con.execute("INSERT OR REPLACE INTO race_weather VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (rid, w.get("weather"), num(w.get("temperature")), num(w.get("windSpeed")), w.get("windDirection"),
                     num(w.get("precipitation")), w.get("targetAt"), rr.get("weather"), num(rr.get("windSpeed")), t))
    except Exception:
        pass
    # 前検日インタビュー（2026-11-10 追加、ユーザー依頼。保存に失敗しても本体の取り込みは止めない）
    try:
        save_interviews(con, q, rid, t, row["cup_id"])
    except Exception:
        pass
    # 選手の条件別の成績（2026-11-10 追加、ユーザー依頼。保存に失敗しても本体の取り込みは止めない）
    try:
        save_rider_stats(con, rd, rid, t)
    except Exception:
        pass
    # オッズ
    odds = {bt: {} for bt in BET_TYPES}
    src_upd = ts(od.get("oddsUpdatedAt"))
    n = 0
    for k, bt in WT_TYPES.items():
        for o in od.get(k, []):
            combo = "-".join(map(str, o["key"]))
            if bt == "ワイド":
                val, vmax = o["minOdds"], o["maxOdds"]
            else:
                val, vmax = o["odds"], None
            if o.get("absent"):
                continue
            odds[bt][combo] = (val, vmax, o.get("popularityOrder"))
            con.execute("INSERT OR IGNORE INTO odds VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (rid, "winticket", bt, combo, val, vmax, o.get("popularityOrder"), src_upd, t, phase))
            n += 1
    meta = {"source": "winticket", "fetched_at": t, "source_updated_at": src_upd,
            "final": od.get("finalOdds"), "aggregated": od.get("isAggregated"), "delayed": od.get("oddsDelayed")}
    # 結果
    if rd.get("results"):
        num_of = {e["playerId"]: e["number"] for e in rd["entries"]}
        for x in rd["results"]:
            con.execute("INSERT OR REPLACE INTO results VALUES(?,?,?,?,?,?,?)",
                        (rid, x["order"], num_of.get(x["playerId"]), x["playerId"], x["factor"], x["margin"], t))
        for k, bt in WT_TYPES.items():
            for wid in rd.get(k + "WinningOddsIds", []):
                combo = wid.split(":")[2].replace(".", "-")
                o = next((o for o in od.get(k, []) if "-".join(map(str, o["key"])) == combo), None)
                if o:
                    pay = o.get("payoffUnitPrice") or round(o["odds"] * 100)
                    con.execute("INSERT OR REPLACE INTO payouts VALUES(?,?,?,?,?,?)",
                                (rid, bt, combo, pay, o.get("popularityOrder"), t))
    con.commit()
    log(con, "winticket", url, rid, 1, n, f"odds_upd={src_upd} final={od.get('finalOdds')}")
    return rd, odds, meta


def fetch_nk_odds(con, row, phase=""):
    rid = row["race_id"]
    nk_id = f"{row['date']}{int(row['venue_id']):02d}{row['race_no']:02d}"
    url = "https://keirin.netkeiba.com/api/race/"
    try:
        r = _get("nk", lambda: requests.post(url, headers={**UA, "Referer": f"https://keirin.netkeiba.com/race/odds/?race_id={nk_id}"},
                                             data={"class": "AplRaceOdds", "method": "get", "compress": "0",
                                                   "race_id": nk_id, "input": "UTF-8", "output": "json"}, timeout=20))
        j = r.json()
        d = j["data"][f"nkrace_odds::{nk_id}"]
        upd = j["data"].get(f"nkrace_odds::{nk_id}_last_dt", "")
    except Exception as e:
        log(con, "netkeirin", url, rid, 0, 0, f"{nk_id} {e!r}")
        return None, None
    t = now().isoformat(timespec="seconds")
    odds = {bt: {} for bt in BET_TYPES}
    n = 0
    for k, bt in NK_TYPES.items():
        for row_ in d.get(k, []):
            c = row_[0]
            combo = "-".join(str(int(c[i:i + 2])) for i in range(0, len(c), 2))
            try:
                val = float(row_[1])
            except ValueError:
                continue
            vmax = float(row_[2]) if row_[2] else None
            odds[bt][combo] = (val, vmax, int(row_[3]) if row_[3] else None)
            con.execute("INSERT OR IGNORE INTO odds VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (rid, "netkeirin", bt, combo, val, vmax, odds[bt][combo][2], str(upd), t, phase))
            n += 1
    con.commit()
    log(con, "netkeirin", url, rid, 1, n, f"{nk_id} last_dt={upd}")
    return odds, {"source": "netkeirin", "fetched_at": t, "source_updated_at": str(upd)}


def nk_race_id(row):
    return f"{row['date']}{int(row['venue_id']):02d}{int(row['race_no']):02d}"


def fetch_nk_comments(con, row):
    """netkeirin の出走表ページ（robots.txt 全許可）の「選手コメント」を rider_comments に保存する（2026-11-10 追加、ユーザー依頼）。
    多くのレースは作戦だけ（「自力。」「〇〇君。」＝WINTICKET の entries.comment とほぼ同じ）だが、決勝など一部のレースでは
    前のレースのあとの談話（「体調も戻り、初日よりも軽かったですね。自力でいく。」など）が入る。
    最初に取れた文を残す（上書きしない。後で短い作戦だけに差し替わることがあるため）。戻り値: 新しく保存した人数（取得失敗は None）"""
    from bs4 import BeautifulSoup
    rid = row["race_id"]
    nk = nk_race_id(row)
    url = f"https://keirin.netkeiba.com/race/entry/?race_id={nk}"
    try:
        r = _get("nk", lambda: requests.get(url, headers=UA, timeout=20))
        r.raise_for_status()
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "lxml")
    except Exception as e:
        log(con, "netkeirin", url, rid, 0, 0, f"comments {nk} {e!r}")
        return None
    t = now().isoformat(timespec="seconds")
    n = 0
    for tr in soup.select("tr.PlayerList"):
        a = tr.select_one("a.Player01[id^=names_]")  # 例: id="names_14089_202611084812"（14089 → WINTICKET の '014089'）
        c = tr.select_one("td.Txt_L")
        if a is None or c is None:
            continue
        parts = a.get("id", "").split("_")
        pid = parts[1].zfill(6) if len(parts) >= 3 and parts[1].isdigit() else None
        num = None
        for td in tr.find_all("td"):  # 車番のマス（class="RaceCardCell01 Waku{車番}"）
            if any(cl.startswith("Waku") and cl[4:].isdigit() for cl in td.get("class") or []):
                s = td.get_text(strip=True)
                num = int(s) if s.isdigit() else None
                break
        if num is None and pid:
            x = con.execute("SELECT number FROM entries WHERE race_id=? AND player_id=?", (rid, pid)).fetchone()
            num = x[0] if x else None
        if num is None:
            continue
        cur = con.execute("INSERT OR IGNORE INTO rider_comments VALUES(?,?,?,?,?,?)",
                          (rid, num, pid, "netkeirin", c.get_text(" ", strip=True), t))
        n += max(cur.rowcount, 0)
    con.commit()
    log(con, "netkeirin", url, rid, 1, n, f"comments {nk}")
    return n


# ---------------------------------------------------------------- 確率モデル（券種間整合）
def tri_probs(odds, alpha=1.0):
    """3連単オッズから市場の推定確率。alpha>1 は大穴を割り引く（大穴過大評価バイアス補正の感度分析用）。
    9999.9（票なし/発売前相当）は除外。"""
    q = {c: (1.0 / o[0]) ** alpha for c, o in odds["3連単"].items() if o[0] and o[0] < 9999}
    s = sum(q.values())
    return {tuple(map(int, c.split("-"))): v / s for c, v in q.items()} if s else {}


def derived(P):
    ex, qu, wi, tr = {}, {}, {}, {}
    for (i, j, k), p in P.items():
        ex[(i, j)] = ex.get((i, j), 0) + p
        a = tuple(sorted((i, j)))
        qu[a] = qu.get(a, 0) + p
        t3 = tuple(sorted((i, j, k)))
        tr[t3] = tr.get(t3, 0) + p
        for pr in itertools.combinations(sorted((i, j, k)), 2):
            wi[pr] = wi.get(pr, 0) + p
    return ex, qu, wi, tr


def model_probs(odds, alpha):
    """各券種の「他プール由来」推定確率。
    2車単/2車複/ワイド/3連複: 3連単プールから集計。
    3連単: 2車単プール(1-2着) × 3連単内の3着条件付き と 3連複プール × 3連単内の着順配分 の平均。"""
    P = tri_probs(odds, alpha)
    if not P:
        return None
    ex, qu, wi, tr = derived(P)
    out = {"2車単": {f"{a}-{b}": p for (a, b), p in ex.items()},
           "2車複": {f"{a}-{b}": p for (a, b), p in qu.items()},
           "ワイド": {f"{a}-{b}": p for (a, b), p in wi.items()},
           "3連複": {"-".join(map(str, t)): p for t, p in tr.items()}}
    # 2車単・3連複プールの確率
    def pool(bt):
        q = {c: (1.0 / o[0]) ** alpha for c, o in odds[bt].items() if o[0] and o[0] < 9999}
        s = sum(q.values())
        return {c: v / s for c, v in q.items()} if s else {}
    pex, ptr = pool("2車単"), pool("3連複")
    t3 = {}
    for (i, j, k), p in P.items():
        a = pex.get(f"{i}-{j}", 0) * (p / ex[(i, j)])
        key = "-".join(map(str, sorted((i, j, k))))
        b = ptr.get(key, 0) * (p / tr[tuple(sorted((i, j, k)))])
        t3[f"{i}-{j}-{k}"] = (a + b) / 2
    out["3連単"] = t3
    return out


def evaluate(odds):
    """全組番の EV を α=1.0 と α=1.15 で算出。保守的に min を採用。"""
    m1, m2 = model_probs(odds, 1.0), model_probs(odds, 1.15)
    if not m1:
        return []
    rows = []
    for bt in BET_TYPES:
        for c, (o, omax, pop) in odds[bt].items():
            if not o or o >= 9999:
                continue
            p1, p2 = m1[bt].get(c, 0), m2[bt].get(c, 0)
            rows.append({"bet_type": bt, "combo": c, "odds": o, "odds_max": omax, "pop": pop,
                         "p": p1, "ev1": p1 * o, "ev2": p2 * o, "evc": min(p1 * o, p2 * o)})
    return rows


def rate(r):
    p, e = r["p"], r["evc"]
    if e >= 1.30 and p >= 0.05:
        return "A+"
    if e >= 1.20 and p >= 0.03:
        return "A"
    if e >= 1.10 and p >= 0.02:
        return "B"
    return "C"


def equivalence_checks(odds):
    """厳密に同一事象となる組合せの合成オッズ比較。
    (1) 2車複 {i,j}  ≡ 2車単 i-j + j-i （相互排他・和集合が一致）
    (2) 3連複 {i,j,k} ≡ 3連単 6通り（相互排他・和集合が一致）
    ※ 3連単の裏表2点と2車複は3着条件が残るので同一事象ではない（比較対象にしない）。"""
    out = []
    for c, (o, _, _) in odds["2車複"].items():
        i, j = c.split("-")
        a, b = odds["2車単"].get(f"{i}-{j}"), odds["2車単"].get(f"{j}-{i}")
        if a and b and o < 9999 and a[0] < 9999 and b[0] < 9999:
            syn = 1 / (1 / a[0] + 1 / b[0])
            out.append({"event": f"1-2着={{{i},{j}}}", "single": ("2車複", c, o), "synthetic": ("2車単2点", syn),
                        "ratio": o / syn})
    for c, (o, _, _) in odds["3連複"].items():
        ks = c.split("-")
        ps = ["-".join(p) for p in itertools.permutations(ks)]
        os_ = [odds["3連単"].get(p) for p in ps]
        if o < 9999 and all(x and x[0] < 9999 for x in os_):
            syn = 1 / sum(1 / x[0] for x in os_)
            out.append({"event": f"1-3着={{{c}}}", "single": ("3連複", c, o), "synthetic": ("3連単6点", syn),
                        "ratio": o / syn})
    return out


# ---------------------------------------------------------------- 6視点（ルールベース）
def six_views(con, row, odds, rows):
    rid = row["race_id"]
    E = [dict(zip([d[0] for d in con.execute("SELECT * FROM entries LIMIT 0").description], x))
         for x in con.execute("SELECT * FROM entries WHERE race_id=? AND absent=0 ORDER BY number", (rid,))]
    lines = json.loads(row["line_json"] or "[]")
    P = tri_probs(odds, 1.0)
    win = {}
    for (i, j, k), p in P.items():
        win[i] = win.get(i, 0) + p
    by_no = {e["number"]: e for e in E}
    pts_rank = {e["number"]: r + 1 for r, e in enumerate(sorted(E, key=lambda e: -(e["race_point"] or 0)))}
    mk_rank = {n: r + 1 for r, (n, _) in enumerate(sorted(win.items(), key=lambda x: -x[1]))}
    lines_s = []
    for ln in lines:
        nums = [n for ent in ln["entries"] for n in ent["numbers"]]
        lines_s.append(nums)
    v = {}
    desc = " / ".join("-".join(f"{n}({(by_no.get(n) or {}).get('style','?')}{(by_no.get(n) or {}).get('race_point') or 0:.0f})"
                               for n in l) for l in lines_s)
    fronts = [l for l in lines_s if l and (by_no.get(l[0]) or {}).get("style") in ("逃", "両")]
    v["展開"] = f"並び予想[{row['line_type']}] {desc}。自力型を先頭とするライン{len(fronts)}本。" + \
        ("主導権争いが激化しやすい。" if len(fronts) >= 3 else "主導権は比較的まとまりやすい。")
    fav = max(win, key=win.get) if win else None
    if fav:
        fl = next((l for l in lines_s if fav in l), [fav])
        pos = fl.index(fav)
        leader = by_no.get(fl[0]) or {}
        v["反対意見"] = (f"本命{fav}番(市場1着率{win[fav]:.0%})。" +
                     (f"番手/後位のため先頭{fl[0]}番(得点{leader.get('race_point') or 0:.1f})が不発なら共倒れ。" if pos > 0 else
                      f"自力型。他ライン{len(lines_s)-1}本の先行・叩き合い、単騎の飛びつきで脚を使わされる展開に弱い。"))
    gaps = [(n, pts_rank[n], mk_rank.get(n, 99)) for n in pts_rank if mk_rank.get(n, 99) - pts_rank[n] >= 2]
    v["前提破壊"] = ("得点順位より市場評価が大きく低い選手: " + ", ".join(f"{n}番(得点{a}位/市場{b}位)" for n, a, b in gaps)
                 if gaps else "得点順位と市場1着評価の順位に大きな乖離なし。")
    hot = []
    for e in E:
        rec = json.loads(e["recent_orders"] or "[]")[-6:]
        if rec and sum(1 for x in rec if 0 < x <= 2) >= 3 and mk_rank.get(e["number"], 99) >= 3:
            hot.append(f"{e['number']}番(直近{rec})")
    v["見落とし"] = ("直近好調だが市場3番手以下: " + ", ".join(hot)) if hot else "直近成績と市場評価の明確なずれは検出せず。"
    return v


# ---------------------------------------------------------------- 判断（B0/B1）
RULE_VERSION = "v2-20261105"
ENABLE_15 = False  # 15点枠 B1T15 の記録（停止中）
# 参照オッズ→確定オッズの下落率（2026-11-04 の B0/B1 実測の中央値。選ばれた組番の値なので保守的に使う）
DRIFT = {"B0": {"ワイド": -0.60, "3連複": -0.55, "2車単": -0.42, "2車複": -0.41, "3連単": -0.30},
         "B1": {"ワイド": -0.42, "3連単": -0.17, "2車複": -0.15, "2車単": -0.15, "3連複": -0.15}}


def front_runner_note(con, row):
    """過去31日の分析: 逃げ型の自力先頭の1着は市場がやや過小評価(比率1.05)、
    先頭が弱いラインの番手の1着は過大評価(0.88)。該当する型かどうかを記録する（購入判断には使わない）"""
    E = {e[0]: e for e in con.execute("SELECT number, style, race_point FROM entries WHERE race_id=? AND absent=0", (row["race_id"],))}
    lines = [[n for x in l["entries"] for n in x["numbers"]] for l in json.loads(row["line_json"] or "[]")]
    if not E or not lines:
        return ""
    top = max(E.values(), key=lambda e: e[2] or 0)
    tl = next((l for l in lines if top[0] in l), [top[0]])
    if tl[0] == top[0] and top[1] == "逃" and len(tl) >= 2:
        return f"[型] 得点トップ{top[0]}番が逃げ型の自力先頭（先行1着がやや割安になりやすい型）。"
    if len(tl) >= 2 and tl[1] == top[0] and (E.get(tl[0], (0, 0, 0))[2] or 0) <= (top[2] or 0):
        return f"[型] 得点トップ{top[0]}番が番手で先頭{tl[0]}番が格下（番手1着が買いかぶられやすい型）。"
    return ""


RULE_TYPES = ("ワイド",)  # 2026-11-06 9月の検証で2車複・3連複は剥がれたため、ワイドのみに絞る


def rule_picks(con, row, odds):
    """法則枠 B1R（2026-11-06〜）。過去32日の確定オッズで回収率147%だった法則に、レース条件を加えたもの。
    レース条件: 7車立て・本命の1着見込み30〜60%・並びが二分戦か三分戦
    買い目: ワイドのうち（2026-11-06〜。それ以前は2車複/3連複も）、3連単の売れ方から見た割安度（見込み）が1.0以上の組番（各100円、最大5点）
    戻り値: (picks, 条件の説明)。条件外なら picks は空"""
    n_car = con.execute("SELECT COUNT(*) FROM entries WHERE race_id=? AND absent=0", (row["race_id"],)).fetchone()[0]
    P = tri_probs(odds, 1.0)
    win = {}
    for (i, j, k), p in P.items():
        win[i] = win.get(i, 0) + p
    fav = max(win.values()) if win else 0
    lt = row["line_type"] or ""
    cond = f"{n_car}車・本命の1着見込み{fav:.0%}・{lt or '並び不明'}"
    if n_car != 7 or not (0.30 <= fav <= 0.60) or lt not in ("二分戦", "三分戦"):
        return [], cond + " → 条件外"
    picks = [r for r in evaluate(odds) if r["bet_type"] in RULE_TYPES and r["evc"] >= 1.0]
    picks.sort(key=lambda r: -r["evc"])
    return picks[:5], cond


def record_rule(con, row, odds, meta):
    """法則枠を締切4〜7分前に判断して記録する（通知と同じ内容）。読み戻しで一致を確認"""
    mins = (row["close_at"] - time.time()) / 60
    if not (0.3 <= mins <= 8.0):  # 2026-11-10〜 締切1分前の判断も受け付ける（11-07〜09は1.5〜8分）
        return None
    picks, cond = rule_picks(con, row, odds)
    created = now().isoformat(timespec="seconds")
    recs = [(r["bet_type"], r["combo"], 100, r["odds"], r["p"], r["ev1"], r["ev2"], f"見込み{r['evc']:.2f}") for r in picks] \
        or [("見送り", "", 0, None, None, None, None, "C")]
    for bt, c, s, o, p, e1, e2, tag in recs:
        sha = hashlib.sha256(f"{row['race_id']}|B1R|{created}|{bt}|{c}|{s}|{o}".encode()).hexdigest()[:16]
        con.execute("""INSERT INTO predictions(race_id,phase,created_at,close_at,minutes_to_close,bet_type,combo,stake,
            ref_odds,ref_source,ref_odds_fetched_at,ref_source_updated_at,model_prob,ev_a10,ev_a115,bet_rating,race_rating,reason,sha)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (row["race_id"], "B1R", created, ts(row["close_at"]), round(mins, 1), bt, c, s, o, meta["source"],
                     meta["fetched_at"], meta["source_updated_at"], p, e1, e2, tag, "R" if picks else "C",
                     json.dumps({"法則枠": cond}, ensure_ascii=False), sha))
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM predictions WHERE race_id=? AND phase='B1R' AND created_at=?",
                    (row["race_id"], created)).fetchone()[0]
    assert n == len(recs), "B1R read-back mismatch"
    return picks, cond, mins


def record_wide(con, row, odds, meta):
    """ワイド枠 B1W（2026-11-06〜）。過去32日の確定オッズで、前半・後半とも100%超だった
    「ワイド × 倍率6〜10倍 × 3連単から見た割安度0.85以上」を全レース対象で各100円（最大5点）。
    法則枠と同じ締切4〜7分前に判断して記録し、読み戻しで一致を確認する"""
    mins = (row["close_at"] - time.time()) / 60
    if not (0.3 <= mins <= 8.0):  # 2026-11-10〜 締切1分前の判断も受け付ける（11-07〜09は1.5〜8分）
        return None
    picks = [r for r in evaluate(odds) if r["bet_type"] == "ワイド" and 6 <= r["odds"] <= 10 and r["evc"] >= 0.85]
    picks.sort(key=lambda r: -r["evc"])
    picks = picks[:5]
    # 新しい点数（2026-11-08〜、表示と記録だけ。選び方は変えない）。判断と同じ時点で計算して記録に残す
    for r in picks:
        try:
            import newscore
            r["score"], r["why"], r["wind"] = newscore.score(con, row, r["combo"], len(picks))
        except Exception:
            r["score"], r["why"], r["wind"] = None, [], None
    created = now().isoformat(timespec="seconds")
    recs = [(r["combo"], 100, r["odds"], r["p"], r["ev1"], r["ev2"],
             f"割安度{r['evc']:.2f}" + (f" 点{r['score']}" if r.get("score") is not None else "")) for r in picks] \
        or [("", 0, None, None, None, None, "C")]
    for c, s, o, p, e1, e2, tag in recs:
        bt = "ワイド" if s else "見送り"
        sha = hashlib.sha256(f"{row['race_id']}|B1W|{created}|{c}|{s}|{o}".encode()).hexdigest()[:16]
        con.execute("""INSERT INTO predictions(race_id,phase,created_at,close_at,minutes_to_close,bet_type,combo,stake,
            ref_odds,ref_source,ref_odds_fetched_at,ref_source_updated_at,model_prob,ev_a10,ev_a115,bet_rating,race_rating,reason,sha)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (row["race_id"], "B1W", created, ts(row["close_at"]), round(mins, 1), bt, c, s, o, meta["source"],
                     meta["fetched_at"], meta["source_updated_at"], p, e1, e2, tag, "W" if picks else "C",
                     json.dumps({"ワイド枠": "ワイド6〜10倍・割安度0.85以上"}, ensure_ascii=False), sha))
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM predictions WHERE race_id=? AND phase='B1W' AND created_at=?",
                    (row["race_id"], created)).fetchone()[0]
    assert n == len(recs), "B1W read-back mismatch"
    return picks


def record_wide_wide(con, row, odds, meta):
    """ワイド枠（広げた版）B3W（2026-11-10〜、ユーザー依頼・記録のみ・通知しない）。締切前の点数を早く貯めるため、
    ワイド枠の範囲を広げた「5〜12倍 × 割安度0.80以上」を各100円（最大8点）。今のワイド枠（6〜10倍・0.85以上）に入る目は
    bet_rating に「内」、広げた分だけの目は「外」と書き、後で分けて集計できるようにする。ワイド枠 B1W には影響しない"""
    mins = (row["close_at"] - time.time()) / 60
    if not (0.3 <= mins <= 8.0):
        return None
    picks = [r for r in evaluate(odds) if r["bet_type"] == "ワイド" and 5 <= r["odds"] <= 12 and r["evc"] >= 0.80]
    picks = sorted(picks, key=lambda r: -r["evc"])[:8]
    created = now().isoformat(timespec="seconds")
    inside = lambda r: 6 <= r["odds"] <= 10 and r["evc"] >= 0.85
    recs = [(r["combo"], 100, r["odds"], r["p"], r["ev1"], r["ev2"], f"割安度{r['evc']:.2f} {'内' if inside(r) else '外'}") for r in picks] \
        or [("", 0, None, None, None, None, "C")]
    for c, s_, o, p, e1, e2, tag in recs:
        sha = hashlib.sha256(f"{row['race_id']}|B3W|{created}|{c}|{s_}|{o}".encode()).hexdigest()[:16]
        con.execute("""INSERT INTO predictions(race_id,phase,created_at,close_at,minutes_to_close,bet_type,combo,stake,
            ref_odds,ref_source,ref_odds_fetched_at,ref_source_updated_at,model_prob,ev_a10,ev_a115,bet_rating,race_rating,reason,sha)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (row["race_id"], "B3W", created, ts(row["close_at"]), round(mins, 1), "ワイド" if s_ else "見送り", c, s_, o, meta["source"],
                     meta["fetched_at"], meta["source_updated_at"], p, e1, e2, tag, "W" if picks else "C",
                     json.dumps({"ワイド枠（広げた版）": "ワイド5〜12倍・割安度0.80以上・最大8点"}, ensure_ascii=False), sha))
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM predictions WHERE race_id=? AND phase='B3W' AND created_at=?", (row["race_id"], created)).fetchone()[0]
    assert n == len(recs), "B3W read-back mismatch"
    return picks


def record_trifecta(con, row, odds, meta):
    """3連単枠 B3T（2026-11-09〜、ユーザー依頼で追加）。tri_rule.py の「形の法則」5つ（3期間すべて100%超え）。
    締切2〜3分前の倍率で判断して各100円（最大6点）を記録し、読み戻しで一致を確認する。ワイド枠・法則枠には影響しない"""
    mins = (row["close_at"] - time.time()) / 60
    if not (0.3 <= mins <= 8.0):  # 2026-11-10〜 締切1分前の判断も受け付ける
        return None
    import tri_rule
    picks = tri_rule.picks(con, row, odds)
    if picks:  # 一番の目（並びの1番目）に出走表の点数をつける（2026-11-09〜、表示と記録だけ。買い目は変えない）
        try:
            picks[0]["top"] = True; picks[0]["score"] = tri_rule.card_score(con, row, picks[0]["combo"])
        except Exception:
            picks[0]["top"] = True; picks[0]["score"] = None
    created = now().isoformat(timespec="seconds")
    recs = [(r["combo"], 100, r["odds"], r["p"], "・".join(r["rules"]) + (f" 一番の目 点{r['score']}" if r.get("top") and r.get("score") is not None else (" 一番の目" if r.get("top") else ""))) for r in picks] or [("", 0, None, None, "C")]
    for c, s_, o, p, tag in recs:
        bt = "3連単" if s_ else "見送り"
        sha = hashlib.sha256(f"{row['race_id']}|B3T|{created}|{c}|{s_}|{o}".encode()).hexdigest()[:16]
        con.execute("""INSERT INTO predictions(race_id,phase,created_at,close_at,minutes_to_close,bet_type,combo,stake,
            ref_odds,ref_source,ref_odds_fetched_at,ref_source_updated_at,model_prob,ev_a10,ev_a115,bet_rating,race_rating,reason,sha)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (row["race_id"], "B3T", created, ts(row["close_at"]), round(mins, 1), bt, c, s_, o, meta["source"],
                     meta["fetched_at"], meta["source_updated_at"], p, None, None, tag, "T" if picks else "C",
                     json.dumps({"3連単枠": tri_rule.RULES}, ensure_ascii=False), sha))
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM predictions WHERE race_id=? AND phase='B3T' AND created_at=?",
                    (row["race_id"], created)).fetchone()[0]
    assert n == len(recs), "B3T read-back mismatch"
    return picks


def record_T(con, row, odds, meta):
    """T枠 B3X（2026-11-10〜、ユーザー依頼・記録のみ・通知しない）。KNOWLEDGE ★事前登録T と同じ条件：
    3連単 10倍以下 ×（G戦 または 9車立て）× 3着の選手の得点順位が5位以下（欠場を除く出走者の競走得点の高い順、同点は小さい順位）。各100円"""
    mins = (row["close_at"] - time.time()) / 60
    if not (0.3 <= mins <= 8.0):
        return None
    if (row["class"] or "") == "L級" or not odds.get("3連単"):
        return []
    G = str(row["grade"] or "").startswith("G"); nine = (row["entries_number"] or 0) >= 9
    if not (G or nine):
        return []
    pts = con.execute("SELECT number, race_point FROM entries WHERE race_id=? AND absent=0", (row["race_id"],)).fetchall()
    vals = sorted([p for _, p in pts if p is not None], reverse=True)
    rank = {n: (1 + sum(1 for v in vals if v > p)) if p is not None else None for n, p in pts}
    picks = []
    for c, (o, _mx, _pop) in odds["3連単"].items():
        if not o or o > 10:
            continue
        d = int(c.split("-")[2])
        if (rank.get(d) or 0) >= 5:
            picks.append({"combo": c, "odds": o})
    created = now().isoformat(timespec="seconds")
    recs = [(p["combo"], 100, p["odds"]) for p in picks] or [("", 0, None)]
    for c, s_, o in recs:
        sha = hashlib.sha256(f"{row['race_id']}|B3X|{created}|{c}|{s_}|{o}".encode()).hexdigest()[:16]
        con.execute("""INSERT INTO predictions(race_id,phase,created_at,close_at,minutes_to_close,bet_type,combo,stake,
            ref_odds,ref_source,ref_odds_fetched_at,ref_source_updated_at,model_prob,ev_a10,ev_a115,bet_rating,race_rating,reason,sha)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (row["race_id"], "B3X", created, ts(row["close_at"]), round(mins, 1), "3連単" if s_ else "見送り", c, s_, o, meta["source"],
                     meta["fetched_at"], meta["source_updated_at"], None, None, None, "T", "T" if picks else "C",
                     json.dumps({"T枠": "10倍以下×(G戦か9車)×3着得点5位以下"}, ensure_ascii=False), sha))
    con.commit()
    return picks


def record_Y(con, row, odds, meta, tri):
    """400m・欠場なしの一番の目 B3Y（2026-11-10〜、ユーザー依頼・記録のみ・通知しない）。KNOWLEDGE ★事前登録Y と同じ条件：
    3連単枠の一番の目（並びの1番目）× 400mバンク（333m系・500mの場を除く）× 欠場なしのレース。100円。条件は変えない"""
    mins = (row["close_at"] - time.time()) / 60
    if not (0.3 <= mins <= 8.0):
        return None
    S333 = {"伊東", "小田原", "松戸", "奈良", "富山", "防府", "前橋"}; S500 = {"宇都宮", "大宮", "高知"}
    top = next((p for p in (tri or []) if p.get("top")), None)
    absent_n = con.execute("SELECT COUNT(*) FROM entries WHERE race_id=? AND absent=1", (row["race_id"],)).fetchone()[0]
    ok = top is not None and (row["venue"] or "") not in (S333 | S500) and absent_n == 0
    created = now().isoformat(timespec="seconds")
    c, s_, o, tag = (top["combo"], 100, top["odds"], "一番の目") if ok else ("", 0, None, "C" if top is None else ("欠場あり" if absent_n else "400m以外"))
    sha = hashlib.sha256(f"{row['race_id']}|B3Y|{created}|{c}|{s_}|{o}".encode()).hexdigest()[:16]
    con.execute("""INSERT INTO predictions(race_id,phase,created_at,close_at,minutes_to_close,bet_type,combo,stake,
        ref_odds,ref_source,ref_odds_fetched_at,ref_source_updated_at,model_prob,ev_a10,ev_a115,bet_rating,race_rating,reason,sha)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (row["race_id"], "B3Y", created, ts(row["close_at"]), round(mins, 1), "3連単" if s_ else "見送り", c, s_, o, meta["source"],
                 meta["fetched_at"], meta["source_updated_at"], top.get("p") if ok else None, None, None, tag, "Y" if ok else "C",
                 json.dumps({"400m・欠場なしの一番の目": "3連単枠の一番の目×400mバンク×欠場なし"}, ensure_ascii=False), sha))
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM predictions WHERE race_id=? AND phase='B3Y' AND created_at=?", (row["race_id"], created)).fetchone()[0]
    assert n == 1, "B3Y read-back mismatch"
    return [top] if ok else []


def record_best(con, row, odds, meta, tri):
    """🏆最強枠 B3S（2026-11-09〜、ユーザー依頼・記録のみ）。3連単枠の一番の目の出走表の点数が3以上のときだけ、
    一番の目の3連単（点数5=500円・3〜4=100円）＋同じ3人の3連複（100円）を記録。読み戻しで一致を確認する"""
    mins = (row["close_at"] - time.time()) / 60
    if not (0.3 <= mins <= 8.0):  # 2026-11-10〜 締切1分前の判断も受け付ける
        return None
    import tri_rule
    top = next((p for p in (tri or []) if p.get("top")), None)
    sc = top.get("score") if top else None
    created = now().isoformat(timespec="seconds")
    recs = []
    if top and sc is not None and sc >= 3:
        a, b, d = top["combo"].split("-"); trio = "-".join(sorted((a, b, d), key=int))
        o3 = (odds.get("3連複", {}).get(trio) or (None,))[0]
        recs = [("3連単", top["combo"], tri_rule.stake_hint(sc), top["odds"], f"一番の目 点{sc}"), ("3連複", trio, 100, o3, f"同じ3人 点{sc}")]
    if not recs:
        recs = [("見送り", "", 0, None, f"点{sc}" if sc is not None else "C")]
    for bt, c, s_, o, tag in recs:
        sha = hashlib.sha256(f"{row['race_id']}|B3S|{created}|{bt}|{c}|{s_}|{o}".encode()).hexdigest()[:16]
        con.execute("""INSERT INTO predictions(race_id,phase,created_at,close_at,minutes_to_close,bet_type,combo,stake,
            ref_odds,ref_source,ref_odds_fetched_at,ref_source_updated_at,model_prob,ev_a10,ev_a115,bet_rating,race_rating,reason,sha)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (row["race_id"], "B3S", created, ts(row["close_at"]), round(mins, 1), bt, c, s_, o, meta["source"],
                     meta["fetched_at"], meta["source_updated_at"], None, None, None, tag, "S" if s_ else "C",
                     json.dumps({"最強枠": "一番の目×点数3以上：3連単（5点500円・3〜4点100円）＋同じ3人の3連複100円"}, ensure_ascii=False), sha))
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM predictions WHERE race_id=? AND phase='B3S' AND created_at=?", (row["race_id"], created)).fetchone()[0]
    assert n == len(recs), "B3S read-back mismatch"
    return recs


def record_watch(con, row, odds, meta):
    """様子見の2枠 B3A（ワイドA）・B3K（形のワイド）（2026-11-09〜、ユーザー依頼）。通知はせず記録だけ。
    締切2〜3分前の倍率で判断して各100円（最大5点）を記録し、読み戻しで一致を確認する"""
    mins = (row["close_at"] - time.time()) / 60
    if not (0.3 <= mins <= 8.0):  # 2026-11-10〜 締切1分前の判断も受け付ける
        return None
    import wide_rule
    res = wide_rule.picks(con, row, odds)
    created = now().isoformat(timespec="seconds")
    for ph, picks in res.items():
        recs = [(r["combo"], 100, r["odds"], r["p"], r["ev"]) for r in picks] or [("", 0, None, None, None)]
        for c, s_, o, p, ev in recs:
            bt = "ワイド" if s_ else "見送り"
            sha = hashlib.sha256(f"{row['race_id']}|{ph}|{created}|{c}|{s_}|{o}".encode()).hexdigest()[:16]
            con.execute("""INSERT INTO predictions(race_id,phase,created_at,close_at,minutes_to_close,bet_type,combo,stake,
                ref_odds,ref_source,ref_odds_fetched_at,ref_source_updated_at,model_prob,ev_a10,ev_a115,bet_rating,race_rating,reason,sha)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (row["race_id"], ph, created, ts(row["close_at"]), round(mins, 1), bt, c, s_, o, meta["source"],
                         meta["fetched_at"], meta["source_updated_at"], p, ev, None, f"割安度{ev:.2f}" if ev else "", "W" if picks else "C",
                         json.dumps({ph: wide_rule.LABELS[ph]}, ensure_ascii=False), sha))
        con.commit()
        n = con.execute("SELECT COUNT(*) FROM predictions WHERE race_id=? AND phase=? AND created_at=?", (row["race_id"], ph, created)).fetchone()[0]
        assert n == len(recs), f"{ph} read-back mismatch"
    return res


def test_track(con, row, odds, meta, rows, mins, excluded):
    """検証買い B1T（データを貯めるための別枠。B0/B1 とは別集計）。B1 と同時刻・同オッズで全レース記録する。
    1) 想定EV最上位（除外帯を除く）に200円
    2) 得点トップの逃げ型が自力先頭のレース: 先頭→番手 2車単 200円、先頭-番手-3番手 3連単 100円"""
    picks = []
    ok = [r for r in rows if not excluded(r)]
    if ok:
        b = max(ok, key=lambda r: r["evc"])
        picks.append((b["bet_type"], b["combo"], 200, b["odds"], b["p"], b["ev1"], b["ev2"], "EV上位"))
    E = {e[0]: e for e in con.execute("SELECT number, style, race_point FROM entries WHERE race_id=? AND absent=0", (row["race_id"],))}
    lines = [[n for x in l["entries"] for n in x["numbers"]] for l in json.loads(row["line_json"] or "[]")]
    if E and lines:
        top = max(E.values(), key=lambda e: e[2] or 0)
        tl = next((l for l in lines if top[0] in l), [])
        if tl and tl[0] == top[0] and top[1] == "逃" and len(tl) >= 2:
            for bt, combo, stake in [("2車単", f"{tl[0]}-{tl[1]}", 200)] + \
                    ([("3連単", f"{tl[0]}-{tl[1]}-{tl[2]}", 100)] if len(tl) >= 3 else []):
                o = odds[bt].get(combo)
                if o and o[0] < 9999 and not any(p[0] == bt and p[1] == combo for p in picks):
                    r = next((x for x in rows if x["bet_type"] == bt and x["combo"] == combo), None)
                    picks.append((bt, combo, stake, o[0], r and r["p"], r and r["ev1"], r and r["ev2"], "先行型"))
        # 番手人気型（2026-11-06〜）: 得点トップが番手で、先頭が逃げ型 → 先頭1着の2車単を他の全員へ各100円
        # 過去31日: 先頭がやや弱いラインの番手1着は過大評価(比率0.88)、逃げ型先頭の1着は過小評価(1.05)
        elif tl and len(tl) >= 2 and tl[1] == top[0] and E.get(tl[0]) and E[tl[0]][1] == "逃":
            lead = tl[0]
            for n in sorted(E):
                combo = f"{lead}-{n}"
                o = odds["2車単"].get(combo)
                if n != lead and o and o[0] < 9999:
                    r = next((x for x in rows if x["bet_type"] == "2車単" and x["combo"] == combo), None)
                    picks.append(("2車単", combo, 100, o[0], r and r["p"], r and r["ev1"], r and r["ev2"], "番手人気型"))
    # 15点枠 B1T15: 想定EV順に15点（各100円）。bet_rating に順位 #1〜#15 を入れ、上位k点ごとの的中率・回収率を比較する
    # 2026-11-05 22時台に停止（ユーザー判断）。過去の B1T15 記録は残す
    ranked = sorted([r for r in ok if r["p"] >= 0.01], key=lambda r: -r["evc"])[:15] if ENABLE_15 else []
    picks15 = [(r["bet_type"], r["combo"], 100, r["odds"], r["p"], r["ev1"], r["ev2"], f"#{i + 1:02d}")
               for i, r in enumerate(ranked)]
    created = now().isoformat(timespec="seconds")
    for bt, c, s, o, p, e1, e2, tag in picks15:
        sha = hashlib.sha256(f"{row['race_id']}|B1T15|{created}|{bt}|{c}|{s}|{o}".encode()).hexdigest()[:16]
        con.execute("""INSERT INTO predictions(race_id,phase,created_at,close_at,minutes_to_close,bet_type,combo,stake,
            ref_odds,ref_source,ref_odds_fetched_at,ref_source_updated_at,model_prob,ev_a10,ev_a115,bet_rating,race_rating,reason,sha)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (row["race_id"], "B1T15", created, ts(row["close_at"]), round(mins, 1), bt, c, s, o, meta["source"],
                     meta["fetched_at"], meta["source_updated_at"], p, e1, e2, tag, "T",
                     json.dumps({"検証買い15点": f"想定EV順の{tag}（データ蓄積用の別枠。ルール{RULE_VERSION}）"}, ensure_ascii=False), sha))
    # 万車券枠 B1M: 倍率100倍以上（払戻1万円以上）の組番から、推定的中率（α=1.15）の高い順に5点（各100円）
    m2 = model_probs(odds, 1.15) or {}
    big = [r for r in rows if r["odds"] >= 100]
    for r in big:
        r["p2"] = m2.get(r["bet_type"], {}).get(r["combo"], 0)
    for i, r in enumerate(sorted(big, key=lambda r: -r["p2"])[:5]):
        sha = hashlib.sha256(f"{row['race_id']}|B1M|{created}|{r['bet_type']}|{r['combo']}|{r['odds']}".encode()).hexdigest()[:16]
        con.execute("""INSERT INTO predictions(race_id,phase,created_at,close_at,minutes_to_close,bet_type,combo,stake,
            ref_odds,ref_source,ref_odds_fetched_at,ref_source_updated_at,model_prob,ev_a10,ev_a115,bet_rating,race_rating,reason,sha)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (row["race_id"], "B1M", created, ts(row["close_at"]), round(mins, 1), r["bet_type"], r["combo"], 100,
                     r["odds"], meta["source"], meta["fetched_at"], meta["source_updated_at"], r["p2"], r["ev1"], r["ev2"],
                     f"#{i + 1}", "M", json.dumps({"万車券枠": f"100倍以上で推定的中率{i + 1}位"}, ensure_ascii=False), sha))
    for bt, c, s, o, p, e1, e2, tag in picks:
        sha = hashlib.sha256(f"{row['race_id']}|B1T|{created}|{bt}|{c}|{s}|{o}".encode()).hexdigest()[:16]
        con.execute("""INSERT INTO predictions(race_id,phase,created_at,close_at,minutes_to_close,bet_type,combo,stake,
            ref_odds,ref_source,ref_odds_fetched_at,ref_source_updated_at,model_prob,ev_a10,ev_a115,bet_rating,race_rating,reason,sha)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (row["race_id"], "B1T", created, ts(row["close_at"]), round(mins, 1), bt, c, s, o, meta["source"],
                     meta["fetched_at"], meta["source_updated_at"], p, e1, e2, tag, "T",
                     json.dumps({"検証買い": f"{tag}（データ蓄積用の別枠。ルール{RULE_VERSION}）"}, ensure_ascii=False), sha))
    con.commit()


def decide(con, row, phase, odds, meta, nk_odds):
    close = row["close_at"]
    mins = (close - time.time()) / 60
    if phase == "B0" and not (30 <= mins <= 90):
        return None
    if phase == "B1" and not (0.5 <= mins < 30):
        return None
    rows = evaluate(odds)
    views = six_views(con, row, odds, rows) if rows else {}
    # 検証
    issues = []
    try:
        age = (now() - dt.datetime.strptime(meta["source_updated_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)).total_seconds() / 60
        if age > 10:
            issues.append(f"オッズ更新から{age:.0f}分経過")
    except Exception:
        issues.append("オッズ更新時刻不明")
    n_none = sum(1 for o in odds["3連単"].values() if o[0] >= 9999)
    if n_none:
        issues.append(f"3連単で票なし{n_none}点")
    diffs = []
    if nk_odds:
        for bt in BET_TYPES:
            for c, o in odds[bt].items():
                x = nk_odds[bt].get(c)
                if x and o[0] and abs(x[0] - o[0]) / o[0] > 0.05:
                    diffs.append((bt, c, o[0], x[0]))
        if diffs:
            issues.append(f"WINTICKET/netkeirin で5%超の差 {len(diffs)}件（更新タイミング差の可能性）")
    else:
        issues.append("netkeirin照合不可")
    views["検証"] = "; ".join(issues) or "鮮度・照合とも問題なし"
    # 候補（ルール v2: 2026-11-04 の検証結果を反映）
    #  - 参照オッズに「確定までの下落率」を掛けた想定オッズで EV を評価する
    #  - 過去31日で回収率が極端に低い帯（3連単300倍以上、ワイド10〜50倍）と FII のワイドは除外する
    for r in rows:
        f = 1 + DRIFT[phase].get(r["bet_type"], -0.3)
        r["odds_adj"] = r["odds"] * f
        r["ev1"], r["ev2"], r["evc"] = r["ev1"] * f, r["ev2"] * f, r["evc"] * f
        r["rating"] = rate(r)
    def excluded(r):
        return ((r["bet_type"] == "3連単" and r["odds"] >= 300) or
                (r["bet_type"] == "ワイド" and (10 <= r["odds"] <= 50 or row["grade"] == "FII")))
    cands = sorted([r for r in rows if r["rating"] != "C" and not excluded(r)], key=lambda r: -r["evc"])
    if row["grade"] == "FII":
        cands = [r for r in cands if r["rating"] in ("A+", "A")]
    views["展開"] = views.get("展開", "") + " " + front_runner_note(con, row)
    if any("票なし" in s for s in issues) and n_none > 20:
        cands = []  # 未成熟プールでは購入しない
    disagreeing = {(bt, c) for bt, c, _, _ in diffs}
    cands = [r for r in cands if (r["bet_type"], r["combo"]) not in disagreeing]
    picks, used, total = [], set(), 0
    for r in cands:
        key = tuple(sorted(r["combo"].split("-")))
        if key in used:
            continue
        stake = {"A+": 300, "A": 200, "B": 100}[r["rating"]]
        if total + stake > 1000 or len(picks) >= 5:
            break
        picks.append((r, stake)); used.add(key); total += stake
    race_rating = picks[0][0]["rating"] if picks else "C"
    top = sorted(rows, key=lambda r: -r["evc"])[:3]
    views["統合"] = (f"{len(picks)}点 計{total}円で購入（評価{race_rating}）。" if picks else "見送り（購入価値を確認できない）。") + \
        " 上位EV: " + ", ".join(f"{r['bet_type']}{r['combo']} {r['odds']}倍 p={r['p']:.3f} EVc={r['evc']:.2f}" for r in top) + \
        "。確率は3連単/2車単/3連複プール間の整合性から導いた市場由来の推定で、独立に校正された勝率モデルではない。" + \
        f" EVは確定までの想定下落を反映（ルール{RULE_VERSION}）。"
    reason = json.dumps(views, ensure_ascii=False)
    created = now().isoformat(timespec="seconds")
    recs = [(r["bet_type"], r["combo"], s, r["odds"], r["p"], r["ev1"], r["ev2"], r["rating"]) for r, s in picks] or \
        [("見送り", "", 0, None, None, None, None, "C")]
    for bt, c, s, o, p, e1, e2, rt in recs:
        sha = hashlib.sha256(f"{row['race_id']}|{phase}|{created}|{bt}|{c}|{s}|{o}".encode()).hexdigest()[:16]
        con.execute("""INSERT INTO predictions(race_id,phase,created_at,close_at,minutes_to_close,bet_type,combo,stake,
            ref_odds,ref_source,ref_odds_fetched_at,ref_source_updated_at,model_prob,ev_a10,ev_a115,bet_rating,race_rating,reason,sha)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (row["race_id"], phase, created, ts(close), round(mins, 1), bt, c, s, o, meta["source"],
                     meta["fetched_at"], meta["source_updated_at"], p, e1, e2, rt, race_rating, reason, sha))
    con.commit()
    # 読み戻し確認
    back = con.execute("SELECT COUNT(*), SUM(stake) FROM predictions WHERE race_id=? AND phase=? AND created_at=?",
                       (row["race_id"], phase, created)).fetchone()
    assert back[0] == len(recs) and (back[1] or 0) == total, "predictions read-back mismatch"
    if phase == "B1":
        test_track(con, row, odds, meta, rows, mins, excluded)
    return {"race_rating": race_rating, "n": len(picks), "total": total, "views": views}
