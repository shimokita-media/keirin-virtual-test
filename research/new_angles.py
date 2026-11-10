"""新しい目線の検証（探す段階・確定オッズ・2025/2〜2026/11）：
⑧地元の選手 ／ ⑥最終日の負け戦の高得点選手 ／ ⑦前のレースからの間隔・遠征 ／ ②締切が重なる時間帯。
選手：市場の見込み（最終の3連単300倍以下から q1=1着・q3=3着以内）と実際を比べる。t=(実際−見込み)/√Σq(1−q)。
回収率：その選手が1着の3連単（300倍以下）を全部100円ずつ。前半（2025）・後半（2026）に分けて同じ向きかも見る。
使い方: python -I -X utf8 research/new_angles.py 出力.md"""
import sys, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
OUT = open(K + sys.argv[1], "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
VP = {"函館": "北海道", "青森": "青森", "いわき平": "福島", "弥彦": "新潟", "前橋": "群馬", "取手": "茨城", "宇都宮": "栃木", "大宮": "埼玉", "西武園": "埼玉",
      "京王閣": "東京", "立川": "東京", "松戸": "千葉", "千葉": "千葉", "川崎": "神奈川", "平塚": "神奈川", "小田原": "神奈川", "伊東": "静岡", "静岡": "静岡",
      "名古屋": "愛知", "岐阜": "岐阜", "大垣": "岐阜", "豊橋": "愛知", "富山": "富山", "松阪": "三重", "四日市": "三重", "福井": "福井", "奈良": "奈良",
      "向日町": "京都", "和歌山": "和歌山", "岸和田": "大阪", "玉野": "岡山", "広島": "広島", "防府": "山口", "高松": "香川", "小松島": "徳島", "高知": "高知",
      "松山": "愛媛", "小倉": "福岡", "久留米": "福岡", "武雄": "佐賀", "佐世保": "長崎", "別府": "大分", "熊本": "熊本"}
AREA = {}
for a, ps in {"北日本": "北海道 青森 岩手 宮城 秋田 山形 福島", "関東": "茨城 栃木 群馬 埼玉 新潟 長野", "南関東": "千葉 東京 神奈川 静岡 山梨",
              "中部": "愛知 岐阜 三重 富山 石川", "近畿": "福井 滋賀 京都 大阪 兵庫 奈良 和歌山", "中国": "岡山 広島 山口 鳥取 島根",
              "四国": "香川 徳島 愛媛 高知", "九州": "福岡 佐賀 長崎 大分 熊本 宮崎 鹿児島 沖縄"}.items():
    for p in ps.split(): AREA[p] = a
RA = pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id")
E = pd.read_pickle(K + "out/side_entries_full.pkl"); E = E[E.absent == 0].drop_duplicates(["race_id", "number"])
R = pd.read_pickle(K + "out/side_results_full.pkl")
Q = pd.read_pickle(K + "out/rider_q.pkl")
T = pd.read_pickle(K + "out/tri_compact.pkl")
E = E.merge(RA[["race_id", "date", "venue", "cup_id", "day_index", "race_type", "grade", "class", "close_at"]], on="race_id").merge(Q, on=["race_id", "number"])
rk = R.drop_duplicates(["race_id", "number"]).set_index(["race_id", "number"])["rank"]
E["rank"] = rk.reindex(list(zip(E.race_id, E.number))).to_numpy()
E = E[E.race_id.isin(set(R.race_id))]
E["y1"] = (E["rank"] == 1).astype(int); E["y3"] = (E["rank"] <= 3).astype(int)
E["half"] = np.where(E.date < "20260101", "〜2025", "2026")
# 300倍以下の組だけから作った見込みは、人気の選手ほど高めに出るので、同じ見込みの高さの選手全体の 実際÷見込み で直す（直した後は全体で1.00）
for k, y in (("q1", "y1"), ("q3", "y3")):
    b = pd.qcut(E[k], 30, duplicates="drop"); f = E.groupby(b, observed=True)[y].sum() / E.groupby(b, observed=True)[k].sum()
    E[k] = E[k] * b.map(f).astype(float)
E["day_index"] = pd.to_numeric(E.day_index, errors="coerce")
# 地元・地区
E["vp"] = E.venue.map(VP)
E["loc"] = np.where(E.prefecture == E.vp, "地元", np.where(E.prefecture.map(AREA) == E.vp.map(AREA), "同じ地区", "他の地区"))
# 得点の順位
E["pt_rank"] = E.groupby("race_id").race_point.rank(ascending=False, method="min")
E["last_day"] = E.day_index == E.groupby("cup_id").day_index.transform("max")
E["rt"] = E.race_type.fillna("")
# 前のレースからの間隔（別の開催の最終出走日から、開催1日目に何日空いたか）
D = E[["player_id", "cup_id", "date"]].drop_duplicates()
cs = D.groupby(["player_id", "cup_id"]).date.agg(["min", "max"]).reset_index().sort_values(["player_id", "min"])
cs["prev_end"] = cs.groupby("player_id")["max"].shift()
cs["gap"] = (pd.to_datetime(cs["min"]) - pd.to_datetime(cs.prev_end)).dt.days
E = E.merge(cs[["player_id", "cup_id", "gap"]], on=["player_id", "cup_id"], how="left")
def row(lab, g):
    if len(g) < 30: return
    r1 = g.y1.sum() / g.q1.sum(); t1 = (g.y1.sum() - g.q1.sum()) / np.sqrt((g.q1 * (1 - g.q1)).sum())
    r3 = g.y3.sum() / g.q3.sum(); t3 = (g.y3.sum() - g.q3.sum()) / np.sqrt((g.q3.clip(0, 1) * (1 - g.q3.clip(0, 1))).sum())
    hh = "・".join(f"{h} {x.y3.sum() / x.q3.sum():.2f}" for h, x in g.groupby("half"))
    P(f"| {lab} | {len(g):,} | {r1:.3f} | {t1:+.1f} | {r3:.3f} | {t3:+.1f} | {hh} |")
def tab(title, groups):
    P(NL + f"### {title}" + NL + "| 区分 | 人数 | 1着 実際÷見込み | t | 3着以内 実際÷見込み | t | 前半・後半（3着以内） |" + NL + "|---|---|---|---|---|---|---|")
    for lab, m in groups: row(lab, E[m])
P(f"# 新しい目線の検証（探す段階・確定オッズ、{E.date.min()}〜{E.date.max()}、{E.race_id.nunique():,}R・選手 {len(E):,}）" + NL)
P("見込みは「同じ見込みの高さの選手全体」で直してある（全体で1.00）。1.00 なら市場どおり。1を超えるほど市場が軽く見ている（割安）。t は ±2 で偶然ではなさそう、±3 でかなり確か（ただしたくさん見ているので ±3 以上を目安に）")
tab("⑧ 地元の選手", [(k, E["loc"] == k) for k in ("地元", "同じ地区", "他の地区")] +
    [("地元×得点1〜2位", (E["loc"] == "地元") & (E.pt_rank <= 2)), ("地元×得点3位以下", (E["loc"] == "地元") & (E.pt_rank >= 3)),
     ("地元×G戦", (E["loc"] == "地元") & E.grade.astype(str).str.startswith("G")), ("地元×最終日", (E["loc"] == "地元") & E.last_day)])
fin = E.rt.str.contains("決勝")
tab("⑥ 最終日の負け戦（決勝以外）の高得点選手", [
    ("最終日×決勝以外×得点1位", E.last_day & ~fin & (E.pt_rank == 1)), ("最終日×決勝以外×得点2位", E.last_day & ~fin & (E.pt_rank == 2)),
    ("最終日×決勝以外×得点3位以下", E.last_day & ~fin & (E.pt_rank >= 3)), ("参考：最終日以外×得点1位", ~E.last_day & (E.pt_rank == 1)),
    ("参考：決勝×得点1位", fin & (E.pt_rank == 1))] +
    [(f"最終日×{k}×得点1位", E.last_day & E.rt.str.contains(k) & (E.pt_rank == 1)) for k in ("一般", "選抜", "特選", "特別優秀", "ガールズ")])
d1 = E.day_index == 1
tab("⑦ 前の開催からの間隔（開催1日目）", [(f"{a}〜{b}日", d1 & E.gap.between(a, b)) for a, b in ((1, 3), (4, 6), (7, 10), (11, 20), (21, 40), (41, 999))] +
    [("間隔不明（初出走など）", d1 & E.gap.isna())])
tab("⑦' 間隔×遠征（開催1日目）", [("中3日以内×他の地区", d1 & (E.gap <= 3) & (E["loc"] == "他の地区")), ("中3日以内×地元", d1 & (E.gap <= 3) & (E["loc"] == "地元")),
                              ("41日以上×得点1〜2位", d1 & (E.gap >= 41) & (E.pt_rank <= 2)), ("41日以上×得点3位以下", d1 & (E.gap >= 41) & (E.pt_rank >= 3))])
# 回収率（その選手が1着の3連単300倍以下）
T = T.merge(E[["race_id", "number", "loc", "pt_rank", "last_day", "rt", "gap", "day_index", "half"]].rename(columns={"number": "a"}), on=["race_id", "a"])
def roi(lab, m):
    g = T[m]
    if len(g) < 100: return
    rr = g.groupby("race_id").ret.mean(); t = (rr.mean() - T.ret.mean()) / (rr.std() / np.sqrt(len(rr)))
    hh = "・".join(f"{h} {x.ret.mean():.0%}" for h, x in g.groupby("half"))
    P(f"| {lab} | {len(g):,} | {g.race_id.nunique():,} | **{g.ret.mean():.0%}** | {t:+.1f} | {hh} |")
P(NL + "### その選手が1着の3連単（300倍以下・全部100円）の回収率" + NL + f"全部の平均 {T.ret.mean():.0%}。t はレースごとの平均と全体の差" + NL)
P("| 区分 | 点数 | レース | 回収率 | t（全体との差） | 前半・後半 |" + NL + "|---|---|---|---|---|---|")
for lab, m in [("地元", T["loc"] == "地元"), ("他の地区", T["loc"] == "他の地区"), ("地元×得点1〜2位", (T["loc"] == "地元") & (T.pt_rank <= 2)),
               ("最終日×決勝以外×得点1位", T.last_day & ~T.rt.str.contains("決勝") & (T.pt_rank == 1)),
               ("最終日以外×得点1位", ~T.last_day & (T.pt_rank == 1)), ("開催1日目×中3日以内", (T.day_index == 1) & (T.gap <= 3)),
               ("開催1日目×41日以上", (T.day_index == 1) & (T.gap >= 41))]:
    roi(lab, m)
# ② 締切が重なる時間帯
ra = RA[RA.race_id.isin(set(T.race_id))][["race_id", "close_at"]].copy(); ra["close_at"] = pd.to_numeric(ra.close_at)
ca = np.sort(ra.close_at.to_numpy())
ra["ov"] = np.searchsorted(ca, ra.close_at + 120, side="right") - np.searchsorted(ca, ra.close_at - 120, side="left") - 1
T2 = pd.read_pickle(K + "out/tri_compact.pkl").merge(ra[["race_id", "ov"]], on="race_id")
T2["ovb"] = pd.cut(T2.ov, [-1, 1, 3, 5, 99], labels=["0〜1", "2〜3", "4〜5", "6以上"])
T2["ob"] = pd.cut(T2.odds, [0, 20, 100, 300], labels=["20倍以下", "20〜100倍", "100〜300倍"])
P(NL + "### ② 締切が前後2分以内に重なる他のレースの数 × 3連単の倍率帯の回収率（全部100円）" + NL)
P("| 重なる数 | レース | 20倍以下 | 20〜100倍 | 100〜300倍 | 全部 |" + NL + "|---|---|---|---|---|---|")
for k, g in T2.groupby("ovb", observed=True):
    v = g.groupby("ob", observed=True).ret.mean()
    P(f"| {k} | {g.race_id.nunique():,} | {v.get('20倍以下', np.nan):.0%} | {v.get('20〜100倍', np.nan):.0%} | {v.get('100〜300倍', np.nan):.0%} | {g.ret.mean():.0%} |")
print("done")
