"""これまで使っていないデータ（選手の条件別の成績 rider_stats・戦法の成功率・レース時の天気/風 race_weather）で、市場の見込みに対する1着・3着内のズレと、1着固定の流し回収率を見る。
期間＝4年目 2022/11/08〜2023/11/07（out/y4/ana.pkl。事前登録の判定は済んで結果も見ているので探す用に使ってよい。5・6年目は判定用に取っておくので使わない）。
rider_stats は過去のレースのページで値が時期とともに変わる＝そのレース時点の数字。"""
import sqlite3, time, json, os, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; S = K + "out/are_work/"
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
a = pd.read_pickle(K + "out/y4/ana.pkl")
ids = sorted(a.race_id.unique())
if not os.path.exists(S + "y4_new.pkl"):
    c = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True, timeout=30)
    RS, W, P, RC = [], [], [], []
    for i in range(0, len(ids), 300):
        q = ids[i:i + 300]; ph = ",".join("?" * len(q))
        RS.append(pd.read_sql(f"SELECT race_id, number, stats_json FROM rider_stats WHERE race_id IN ({ph})", c, params=q))
        W.append(pd.read_sql(f"SELECT race_id, race_weather, race_wind FROM race_weather WHERE race_id IN ({ph})", c, params=q))
        P.append(pd.read_sql(f"SELECT race_id, bet_type, combo, payout FROM payouts WHERE bet_type IN ('3連単','2車単') AND race_id IN ({ph})", c, params=q))
        RC.append(pd.read_sql(f"SELECT race_id, start_at FROM races WHERE race_id IN ({ph})", c, params=q)); time.sleep(0.3)
    c.close()
    pd.to_pickle(tuple(pd.concat(x) for x in (RS, W, P, RC)), S + "y4_new.pkl")
RS, W, P, RC = pd.read_pickle(S + "y4_new.pkl")
print("rider_stats", len(RS), "weather", len(W), W.race_weather.value_counts().to_dict())
J = RS.stats_json.apply(json.loads)
def rate(v, k="t3"):
    if not isinstance(v, list) or sum(v) == 0: return np.nan, 0
    n = sum(v); return ((v[0] + v[1] + v[2]) / n if k == "t3" else v[0] / n), n
X = pd.DataFrame({"race_id": RS.race_id.values, "number": RS.number.values})
keys = ["linePositionFirst", "linePositionSecond", "linePositionThird", "lineSingleHorseman", "lineCompete", "trackDistance333", "trackDistance400", "trackDistance500",
        "hourTypeNormal", "hourTypeMorning", "hourTypeNight", "hourTypeMidnight", "weatherSunny", "weatherCloudy", "weatherRainy",
        "raceTypeQualifyingRound", "raceTypeSemifinal", "raceTypeFinal", "raceTypeLoserRound", "raceTypeSpecial"]
for k in keys:
    X[k] = J.apply(lambda j: j.get(k)).values
for k in ["exSpurt", "exThrust", "exLeftBehind", "exSplitLine", "exSnatch", "exCompete"]:
    X[k + "_n"] = J.apply(lambda j: (j.get(k) or [0, 0])[0]).values
    X[k + "_ok"] = J.apply(lambda j: (j.get(k) or [0, 0])[1]).values
X["all"] = J.apply(lambda j: [j.get("first", 0), j.get("second", 0), j.get("third", 0), j.get("others", 0)]).values
X["home"] = J.apply(lambda j: j.get("hasHome")).values
X["gearmod"] = J.apply(lambda j: j.get("hasModifiedGearRatio")).values
D = a.merge(X, on=["race_id", "number"], how="inner").merge(W, on="race_id", how="left").merge(RC, on="race_id", how="left")
# 今日の条件
S333 = {"伊東", "小田原", "松戸", "奈良", "富山", "防府", "前橋"}; S500 = {"宇都宮", "大宮", "高知"}
D["bank"] = np.where(D.venue.isin(S333), "trackDistance333", np.where(D.venue.isin(S500), "trackDistance500", "trackDistance400"))
D["poskey"] = np.where(D.single, "lineSingleHorseman", np.where(D.pos == 0, "linePositionFirst", np.where(D.pos == 1, "linePositionSecond", "linePositionThird")))
hr = pd.to_datetime(D.start_at, unit="s", utc=True).dt.tz_convert("Asia/Tokyo").dt.hour
D["hourkey"] = np.select([hr < 10, hr >= 21, hr >= 17], ["hourTypeMorning", "hourTypeMidnight", "hourTypeNight"], "hourTypeNormal")
D["wxkey"] = D.race_weather.map({"晴れ": "weatherSunny", "曇り": "weatherCloudy", "雨": "weatherRainy", "小雨": "weatherRainy"})
D["rtkey"] = D.race_type.map(lambda s: "raceTypeFinal" if "決勝" in str(s) else "raceTypeSemifinal" if "準決" in str(s) else "raceTypeQualifyingRound" if "予選" in str(s) else "raceTypeLoserRound" if ("選抜" in str(s) or "一般" in str(s)) else "raceTypeSpecial" if "特" in str(s) else None)
allr = D["all"].apply(lambda v: rate(v)[0]); allw = D["all"].apply(lambda v: rate(v, "w")[0])
def cond_diff(keycol, kind="t3", nmin=5):
    out = []
    for v, k, base_t3, base_w in zip(D.apply(lambda r: r[r[keycol]] if isinstance(r[keycol], str) and r[keycol] in r else None, axis=1), D[keycol], allr, allw):
        r_, n = rate(v, kind)
        out.append(r_ - (base_t3 if kind == "t3" else base_w) if n >= nmin else np.nan)
    return pd.Series(out, index=D.index)
D["d_pos"] = cond_diff("poskey"); D["d_bank"] = cond_diff("bank"); D["d_hour"] = cond_diff("hourkey"); D["d_wx"] = cond_diff("wxkey"); D["d_rt"] = cond_diff("rtkey")
D["d_pos_w"] = cond_diff("poskey", "w")
for k in ["exSpurt", "exThrust", "exLeftBehind", "exSplitLine", "exSnatch", "exCompete"]:
    D[k + "_rate"] = np.where(D[k + "_n"] >= 3, D[k + "_ok"] / D[k + "_n"].replace(0, np.nan), np.nan)
D["lb_rate"] = D.exLeftBehind_n / D["all"].apply(lambda v: max(sum(v), 1))  # 置いていかれた回数÷出走
# 結果・払戻
pay = P[P.bet_type == "3連単"].groupby("race_id").agg(win=("combo", "first"), pay=("payout", "max"), nw=("combo", "size"))
pay = pay[pay.nw == 1]; ex = P[P.bet_type == "2車単"].groupby("race_id").payout.max()
D = D.join(pay, on="race_id").dropna(subset=["win"])
D["w1"] = D.win.str.split("-").str[0].astype(int); D["is1"] = D.number == D.w1; D["in3"] = D["rank"].between(1, 3)
D["tri_ret"] = np.where(D.is1, D.pay, 0); D["tri_cost"] = (D.n - 1) * (D.n - 2) * 100
D["ex_ret"] = np.where(D.is1, D.race_id.map(ex), 0); D["ex_cost"] = (D.n - 1) * 100
fav = D.groupby("race_id").p1.transform("max")
D["are"] = (D.nlines >= 4) & (fav <= 0.35)  # 荒れ予想の近似：1着の本命の見込みが35%以下×4ライン以上
D["half"] = np.where(D.date < "20230508", "前", "後")
print("選手", len(D), "レース", D.race_id.nunique(), "荒れ予想レース", D[D.are].race_id.nunique(), "3連単100倍以上", round(100 * (D.drop_duplicates('race_id').pay >= 10000).mean(), 1))
def summ(x):
    o = {"選手数": len(x), "見込み1着%": 100 * x.p1.mean(), "1着の比": x.is1.mean() / x.p1.mean(), "3着内の比": x.in3.mean() / x.p3.mean(),
         "3連単1着流し%": 100 * x.tri_ret.sum() / x.tri_cost.sum(), "2車単1着流し%": 100 * x.ex_ret.sum() / x.ex_cost.sum()}
    for h in ["前", "後"]:
        y = x[x.half == h]; o["流し" + h] = 100 * y.tri_ret.sum() / y.tri_cost.sum() if len(y) else np.nan
    return pd.Series(o).round(2)
qs = lambda s: pd.qcut(s.rank(method="first"), 5, labels=["低い", "やや低い", "中", "やや高い", "高い"])
feats = {"今日の位置での3着内率−全体（位置別の得意）": "d_pos", "今日の位置での1着率−全体": "d_pos_w", "今日のバンク距離での得意": "d_bank", "今日の時間帯での得意": "d_hour",
         "今日の天気での得意": "d_wx", "今日のレースの種類での得意": "d_rt", "捲りの成功率": "exSpurt_rate", "突っ張りの成功率": "exThrust_rate",
         "置いていかれた割合": "lb_rate", "ライン分断の成功率": "exSplitLine_rate", "競りの成功率": "exCompete_rate"}
ntest, hits = 0, []
for ty in ["全レース", "荒れ予想"]:
    sub0 = D if ty == "全レース" else D[D.are]
    for name, col in feats.items():
        sub = sub0.dropna(subset=[col])
        if len(sub) < 1500: continue
        t = sub.groupby(qs(sub[col]), observed=True).apply(summ); ntest += len(t)
        print(f"\n-- {name}（{ty}）  値の範囲 {sub[col].quantile([.2,.4,.6,.8]).round(3).tolist()}"); print(t.to_string())
        for idx, r in t.iterrows():
            if r["流し前"] > 100 and r["流し後"] > 100: hits.append((ty, name, idx, r.選手数, r["3連単1着流し%"], r["流し前"], r["流し後"]))
for ty in ["全レース", "荒れ予想"]:
    sub = D if ty == "全レース" else D[D.are]
    for name, col in [("地元", "home"), ("ギアの変更", "gearmod")]:
        t = sub.groupby(col).apply(summ); ntest += len(t); print(f"\n-- {name}（{ty}）"); print(t.to_string())
print("\n=== レース時の天気・風（レース単位：3連単100倍以上の割合、一番人気の見込みの帯ごと）===")
rr = D.drop_duplicates("race_id").copy(); rr["fav"] = rr.race_id.map(D.groupby("race_id").p1.max())
rr["big"] = rr.pay >= 10000; rr["fb"] = pd.cut(rr.fav, [0, .35, .5, 1])
print(rr.groupby(["race_weather", "fb"], observed=True).big.agg(["size", "mean"]).round(3).unstack().to_string())
print(rr.groupby([pd.cut(rr.race_wind, [-1, 2, 4, 6, 99]), "fb"], observed=True).big.agg(["size", "mean"]).round(3).unstack().to_string())
print("\n試した区分", ntest); print("前半・後半とも流し100%超え:"); [print(h) for h in hits]
