"""EuroLeague Defense vs Position: Streamlit dashboard.

Reads the tables that `python -m src.build` writes to output/. On Streamlit
Community Cloud they come from the repository itself, which GitHub Actions
updates every day.
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
SEASON = "2026-27"
POSITIONS = ["Guard", "Forward", "Center"]
WINDOWS = [3, 5, 10]
LABEL = {"Guard": "Guards", "Forward": "Forwards", "Center": "Centers"}

st.set_page_config(page_title="EuroLeague Defense vs Position", page_icon="🏀", layout="wide")


@st.cache_data(ttl=3600)
def load():
    recent = pd.read_csv(OUT / f"dvp_recent_{SEASON}.csv")
    season = pd.read_csv(OUT / f"dvp_{SEASON}.csv")
    by_game = pd.read_csv(OUT / f"dvp_by_game_{SEASON}.csv")
    meta = json.loads((OUT / "meta.json").read_text(encoding="utf-8"))
    return recent, season, by_game, meta


def shade(col: pd.Series) -> list[str]:
    """Red = allows more than the league average for that column, blue = less."""
    mean = col.mean()
    styles = []
    for v in col:
        r = v / mean - 1 if mean else 0
        a = min(abs(r) / 0.35, 1) * 0.55
        rgb = "220, 38, 38" if r > 0 else "37, 99, 235"
        styles.append(f"background-color: rgba({rgb}, {a:.2f})")
    return styles


def shade_pct(col: pd.Series) -> list[str]:
    out = []
    for v in col:
        a = min(abs(v) / 40, 1) * 0.55
        rgb = "220, 38, 38" if v > 0 else "37, 99, 235"
        out.append(f"background-color: rgba({rgb}, {a:.2f})")
    return out


recent, season, by_game, meta = load()
names = meta.get("team_names", {})

# ---------------------------------------------------------------- header
st.title("EuroLeague Defense vs Position")
extra = meta.get("games_after_last_complete_round", 0)
rounds = f"rounds 1–{meta['last_complete_round']}" + (f" + {extra} games of round {meta['last_complete_round'] + 1}" if extra else "")
st.caption(
    f"{SEASON} regular season · {meta['games']} games ({rounds}) · data updated "
    f"{meta.get('data_updated_utc', '?')} UTC · positions from EuroLeague Fantasy"
)

c1, c2, c3 = st.columns(3)
for col, pos in zip((c1, c2, c3), POSITIONS):
    t = recent[recent["weakest_vs"] == pos].head(1)
    if t.empty:
        col.metric(f"Weakest vs {LABEL[pos].lower()}", "—")
    else:
        r = t.iloc[0]
        col.metric(f"Weakest vs {LABEL[pos].lower()}", r["team_name"],
                   f"{r['weakest_vs_pct']:+.0f}% vs league average", delta_color="inverse")

tab_form, tab_team, tab_season, tab_method = st.tabs(
    ["Recent form", "Team detail", "Season (opponent-adjusted)", "Method"])

# ---------------------------------------------------------------- recent form
with tab_form:
    st.markdown("Points per game allowed to opposing **guards, forwards and centers** over each team's "
                "last 3, 5 and 10 games. **Red** = more than the league average for that column, "
                "**blue** = less. The last column is the position the team is weakest against.")
    f1, f2 = st.columns([1, 2])
    focus = f1.radio("Show", ["All positions"] + [LABEL[p] for p in POSITIONS], horizontal=True)
    sort_by = f2.selectbox("Sort by", ["Biggest weakness"] + [f"{LABEL[p]} last {n}" for p in POSITIONS for n in WINDOWS])

    view = recent.copy()
    if sort_by != "Biggest weakness":
        pos_label, _, n = sort_by.rpartition(" last ")
        pos = next(p for p in POSITIONS if LABEL[p] == pos_label)
        view = view.sort_values(f"{pos.lower()}_last{n}", ascending=False)

    shown = POSITIONS if focus == "All positions" else [p for p in POSITIONS if LABEL[p] == focus]
    stat_cols = [f"{p.lower()}_last{n}" for p in shown for n in WINDOWS]
    rename = {f"{p.lower()}_last{n}": f"{LABEL[p]} L{n}" for p in POSITIONS for n in WINDOWS}
    rename.update(team_name="Team", games="Games", weakest_vs="Weakest vs", weakest_vs_pct="vs avg %")

    table = view[["team_name", "games"] + stat_cols + ["weakest_vs", "weakest_vs_pct"]].copy()
    table["weakest_vs"] = table["weakest_vs"].map(LABEL)
    table = table.rename(columns=rename)
    styled = (table.style
              .apply(shade, subset=[rename[c] for c in stat_cols])
              .apply(shade_pct, subset=["vs avg %"])
              .format({rename[c]: "{:.1f}" for c in stat_cols} | {"vs avg %": "{:+.0f}%"}))
    st.dataframe(styled, hide_index=True, width="stretch", height=740)
    st.caption("Early in the season L10 covers every game played so far.")

# ---------------------------------------------------------------- team detail
with tab_team:
    team = st.selectbox("Team", sorted(recent["team_name"]))
    code = recent.loc[recent["team_name"] == team, "defense"].iloc[0]
    row = recent[recent["defense"] == code].iloc[0]

    m = st.columns(4)
    for i, pos in enumerate(POSITIONS):
        league = recent[f"{pos.lower()}_last5"].mean()
        m[i].metric(f"{LABEL[pos]} allowed, last 5", f"{row[f'{pos.lower()}_last5']:.1f}",
                    f"{row[f'{pos.lower()}_last5'] - league:+.1f} vs league", delta_color="inverse")
    m[3].metric("Weakest vs", LABEL[row["weakest_vs"]], f"{row['weakest_vs_pct']:+.0f}% vs league average",
                delta_color="inverse")

    g = by_game[(by_game["defense"] == code) & (by_game["position"].isin(POSITIONS))]
    games = (g.pivot_table(index=["game_code", "round", "offense"], columns="position",
                           values="pts", aggfunc="sum", fill_value=0)
              .reindex(columns=POSITIONS, fill_value=0).reset_index().sort_values("game_code"))
    # zero-padded round keeps the chart in game order (R01, R02 ... R10)
    games["Game"] = ("R" + games["round"].astype(int).map("{:02d}".format) + " vs "
                     + games["offense"].map(names).fillna(games["offense"]))

    st.markdown(f"**Points allowed by position, game by game**")
    chart = games.set_index("Game")[POSITIONS].rename(columns=LABEL)
    st.bar_chart(chart, stack=False, height=360, color=["#4C78A8", "#F58518", "#54A24B"])

    detail = games[["Game"] + POSITIONS].rename(columns=LABEL).iloc[::-1]
    detail["Total"] = detail[[LABEL[p] for p in POSITIONS]].sum(axis=1)
    st.dataframe(detail, hide_index=True, width="stretch")

# ---------------------------------------------------------------- season
with tab_season:
    st.markdown("Whole season, one row per team and position. **Over expected** compares the points "
                "allowed with what the same players usually score in those minutes, so a team that "
                "faced strong scorers is not marked as a weak defense for that alone. Rank 1 = weakest.")
    pos = st.radio("Position", POSITIONS, format_func=lambda p: LABEL[p], horizontal=True, key="season_pos")
    s = season[season["position"] == pos][[
        "rank", "team_name", "games", "pts_allowed", "pts_index", "pts_per40",
        "pts_over_expected", "pir_allowed", "pir_over_expected", "reb_allowed", "ast_allowed", "fg3m_allowed",
    ]]
    st.dataframe(
        s, hide_index=True, width="stretch", height=740,
        column_config={
            "rank": "Rank", "team_name": "Team", "games": "Games",
            "pts_allowed": st.column_config.NumberColumn("Pts allowed", format="%.1f"),
            "pts_index": st.column_config.NumberColumn("vs league", format="%.2f×"),
            "pts_per40": st.column_config.NumberColumn("Pts / 40 min", format="%.1f"),
            "pts_over_expected": st.column_config.NumberColumn("Pts over expected", format="%+.1f"),
            "pir_allowed": st.column_config.NumberColumn("PIR allowed", format="%.1f"),
            "pir_over_expected": st.column_config.NumberColumn("PIR over expected", format="%+.1f"),
            "reb_allowed": st.column_config.NumberColumn("Reb", format="%.1f"),
            "ast_allowed": st.column_config.NumberColumn("Ast", format="%.1f"),
            "fg3m_allowed": st.column_config.NumberColumn("3PM", format="%.1f"),
        },
    )

# ---------------------------------------------------------------- method
with tab_method:
    st.markdown("""
**Data.** Box scores from [euroleague-fantasy-data](https://github.com/straledev/euroleague-fantasy-data).
Every game there is checked against the official final score before it is published. Positions
(guard, forward, center) are the ones used in the EuroLeague Fantasy game.

**Points allowed.** For each game, the points of all opposing players of one position are added up.
The tables only update when, in every game, the points by position add up exactly to the
opponent's final score.

**Weakest vs.** Guards always score the most, so raw points can't say which position a team
struggles with. Each figure is compared with the league average for the same position and window,
the three windows are averaged, and the position furthest above average is shown.

**Opponent adjustment (season tab).** Each player's expected points are his points per minute in his
*other* games this season, times his minutes in this game, pulled towards the position average when
he has played little.

**Caution.** After about 10 games per team, differences of 2–3 points can still be noise.

Code: [euroleague-defense-vs-position](https://github.com/straledev/euroleague-defense-vs-position)
""")