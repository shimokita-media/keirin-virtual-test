"""本番の記録（11/6〜）の枠ごとの成績を集計する（2026-11-11 作成）。本番DBのコピー out/live_db/keirin.sqlite を読むだけ。
払戻は確定の払戻（payouts）。判断後に買い目の選手が欠場したら返還＝100円（notify.pay_of と同じ）。確定していないレースは除く。
使い方: python -I -X utf8 research/forward_status.py 出力.md"""
import sys, sqlite3, datetime as dt, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; LDB = K + "out/live_db/keirin.sqlite"; NL = chr(10)
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
con = sqlite3.connect("file:" + LDB + "?mode=ro", uri=True)
pr = pd.read_sql("""SELECT p.pred_id, p.race_id, p.phase, p.created_at, p.minutes_to_close, p.bet_type, p.combo, p.stake, p.ref_odds,
    p.bet_rating, r.date FROM predictions p JOIN races r USING(race_id) WHERE p.stake>0 AND r.date>='20261106'""", con)
pay = pd.read_sql("SELECT race_id, bet_type, combo, payout FROM payouts", con)
settled = set(pay.race_id)
ab = pd.read_sql("SELECT race_id, number FROM entries WHERE absent=1", con)
absent = ab.groupby("race_id").number.apply(set).to_dict()
pr = pr[pr.race_id.isin(settled)].copy()
pr = pr.merge(pay, on=["race_id", "bet_type", "combo"], how="left")
def refund(r):
    if pd.notna(r.payout): return r.payout
    nums = {int(x) for x in str(r.combo).split("-") if x.isdigit()}
    return 100 if nums & absent.get(r.race_id, set()) else 0
pr["hit"] = pr.payout.notna()
pr["ret"] = pr.apply(refund, axis=1) / 100.0 * pr.stake / 100.0   # 100円あたりの払戻（倍）×口数
pr["n"] = pr.stake / 100.0
# 1つのレース・枠で判断が2回以上記録されていないか
dup = pr.groupby(["race_id", "phase"]).created_at.nunique()
ndup = (dup > 1).sum()
rng = np.random.default_rng(0)
def stats(g):
    n = g.n.sum(); ret = g.ret.sum()
    if n == 0: return None
    # 1点ごとの払戻（100円＝1）。stake が100円以外の行は口数で重みをつけて展開
    x = np.repeat((g.ret / g.n).to_numpy(), g.n.astype(int).to_numpy())
    roi = ret / n; sd = x.std(ddof=1) if len(x) > 1 else np.nan
    t = (roi - 1) / (sd / np.sqrt(n)) if sd and sd > 0 else np.nan
    by = g.groupby("race_id")[["ret", "n"]].sum(); s, m = by.ret.to_numpy(), by.n.to_numpy(); R = len(by)
    idx = rng.integers(0, R, (10000, R)); boot = s[idx].sum(1) / m[idx].sum(1)
    w = rng.dirichlet(np.ones(R), 10000); post = (w @ s) / (w @ m)
    return dict(races=R, n=int(n), hits=int(g.hit.sum()), roi=roi, sd=sd, t=t, lo=np.percentile(boot, 2.5), hi=np.percentile(boot, 97.5),
                p=(post > 1).mean(), p95=(post * 0.95 > 1).mean(), days=g.date.nunique(), first=g.date.min(), last=g.date.max())
F = [("B1W", "ワイド枠", pr.phase == "B1W"),
     ("B3W", "広げたワイド枠（全部）", pr.phase == "B3W"),
     ("B3W内", "広げたワイド枠の内（＝ワイド枠の範囲）", (pr.phase == "B3W") & pr.bet_rating.str.contains("内", na=False)),
     ("B3W外", "広げたワイド枠の外（広げた分だけ）", (pr.phase == "B3W") & pr.bet_rating.str.contains("外", na=False)),
     ("B3T", "3連単枠（全部）", pr.phase == "B3T"),
     ("B3T一番", "3連単枠の一番の目", (pr.phase == "B3T") & pr.bet_rating.str.contains("一番の目", na=False)),
     ("B3X", "T枠（記録のみ）", pr.phase == "B3X"),
     ("B3Y", "400m・欠場なしの一番の目（記録のみ）", pr.phase == "B3Y"),
     ("B1R", "法則枠", pr.phase == "B1R"),
     ("B3A", "ワイドA（様子見）", pr.phase == "B3A"),
     ("B3K", "形のワイド（様子見）", pr.phase == "B3K"),
     ("B3S", "最強枠（記録のみ）", pr.phase == "B3S")]
TARGET = {"B3X": 3500, "B3Y": 3500, "B1W": 1000, "B3W": 1000, "B3W内": 1000}
last_day = pr.date.max()
P(f"# 本番の記録の成績（{pr.date.min()[4:6]}/{pr.date.min()[6:]}〜{last_day[4:6]}/{last_day[6:]}、確定したレースだけ）" + NL)
P(f"作成 {dt.datetime.now():%Y-%m-%d %H:%M}。本番DB（GitHub リリース db）のコピーを集計。払戻は確定の払戻、各100円（最強枠は口数どおり）。"
  "返還（判断後の欠場）は100円で戻ったものとして数え、当たりには数えない。実際の購入はしていない（仮想）。" + NL)
P("- 標準偏差＝1点（100円）あたりの払戻のばらつき（倍）。t値＝(回収率−1)÷(標準偏差÷√点数)（同じレースの目どうしの相関は無視）")
P("- 95%の範囲＝レース単位のブートストラップ（1万回）。P(>100%)＝レース単位のベイズ・ブートストラップで本当の回収率が100%を超える確率。目減り5%込み＝払戻×0.95")
if ndup: P(f"- 注意：同じレース・枠で判断が2回以上記録されたものが {ndup} 件ある（そのまま全部数えた）")
P("")
P("## 1. 枠ごとのまとめ（全期間）" + NL)
P("| 枠 | 内容 | 期間 | レース | 点数 | 当たり | 回収率 | 標準偏差 | t値 | 95%の範囲 | P(>100%) | 目減り5%込み |" + NL + "|---|---|---|---|---|---|---|---|---|---|---|---|")
S = {}
for k, lab, m in F:
    s = stats(pr[m]); S[k] = s
    if s is None: P(f"| {k} | {lab} | — | 0 | 0 | — | — | — | — | — | — | — |"); continue
    P(f"| {k} | {lab} | {s['first'][4:6]}/{s['first'][6:]}〜 | {s['races']} | {s['n']:,} | {s['hits']} | **{s['roi']:.0%}** | {s['sd']:.2f} | {s['t']:+.2f} | {s['lo']:.0%}〜{s['hi']:.0%} | **{s['p']:.0%}** | {s['p95']:.0%} |")
P("")
P("## 2. 締切1分前の判断だけ（判断時刻が締切1.5分前以内。11/10〜）" + NL)
P("11/6〜9 は判断が締切2〜7分前だったので、本番と同じ「1分前」の分だけを別に出す。" + NL)
P("| 枠 | レース | 点数 | 当たり | 回収率 | 標準偏差 | t値 | 95%の範囲 | P(>100%) | 目減り5%込み |" + NL + "|---|---|---|---|---|---|---|---|---|---|")
one = pr.minutes_to_close <= 1.5
for k, lab, m in F:
    s = stats(pr[m & one])
    if s is None: continue
    P(f"| {k} {lab} | {s['races']} | {s['n']:,} | {s['hits']} | **{s['roi']:.0%}** | {s['sd']:.2f} | {s['t']:+.2f} | {s['lo']:.0%}〜{s['hi']:.0%} | **{s['p']:.0%}** | {s['p95']:.0%} |")
P("")
P("## 3. 目安の点数までの見込み" + NL)
P("B3X・B3Y は「偶然でないと言うには約3,500点」、ワイド枠は「1,000点」が目安。ペース＝記録が始まってからの1日あたりの点数（確定済みの日）。" + NL)
P("| 枠 | 目安 | 今の点数 | 達成率 | 1日あたり | 残り | 到達の見込み |" + NL + "|---|---|---|---|---|---|---|")
for k, tg in TARGET.items():
    s = S.get(k)
    if not s: continue
    d0 = dt.datetime.strptime(s["first"], "%Y%m%d"); d1 = dt.datetime.strptime(s["last"], "%Y%m%d")
    ndays = (d1 - d0).days + 1; pace = s["n"] / ndays; rest = max(0, tg - s["n"])
    eta = "到達済み" if rest == 0 else f"{(d1 + dt.timedelta(days=int(np.ceil(rest / pace)))):%Y-%m-%d} ごろ（あと約{int(np.ceil(rest / pace))}日）"
    P(f"| {k} | {tg:,} | {s['n']:,} | {s['n'] / tg:.0%} | {pace:.0f}点 | {rest:,} | {eta} |")
P("")
P("### B3X・B3Y は本番ではまだ0点。過去のペースからの見込み" + NL)
P("B3X（T枠）は G戦か9車立てのレースだけが対象。11/10 は G戦・9車立てが1つもなく（F1・F2 の7車中心）、記録が始まったのが11/10なので0点。"
  "B3Y は 11/10 22:13 からの記録で、8レース判断して条件に合う一番の目はなし。" + NL)
P("2024年の正式な判定（2023/11/08〜2025/01/31・451日、最終オッズ）での点数から、本番でも同じくらい出ると仮定すると：" + NL)
P("| 枠 | 2024年の点数 | 1日あたり | 3,500点までの日数 | 到達の見込み |" + NL + "|---|---|---|---|---|")
for k, n24 in (("B3X", 890), ("B3Y", 1971)):
    pace = n24 / 451; dd = int(np.ceil(3500 / pace))
    P(f"| {k} | {n24:,} | {pace:.1f}点 | 約{dd:,}日（約{dd / 365:.1f}年） | {(dt.datetime(2026, 11, 10) + dt.timedelta(days=dd)):%Y年%m月}ごろ |")
P(NL + "→ 3,500点は年単位でかかる。G戦の開催がある週に固まって増える（T枠は G戦か9車立てだけなので、F戦だけの日は0点）。" + NL)
P("## 4. 日ごとの回収率（点数・当たり・回収率）" + NL)
days = sorted(pr.date.unique())
P("| 枠 | " + " | ".join(f"{d[4:6]}/{d[6:]}" for d in days) + " |" + NL + "|---|" + "---|" * len(days))
for k, lab, m in F:
    g = pr[m]
    if g.empty: continue
    cells = []
    for d in days:
        h = g[g.date == d]
        cells.append("—" if h.empty else f"{h.n.sum():.0f}点 {int(h.hit.sum())}本 {h.ret.sum() / h.n.sum():.0%}")
    P(f"| {k} | " + " | ".join(cells) + " |")
P("")
OUT.close()
