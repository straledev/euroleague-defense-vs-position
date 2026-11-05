"""Defense vs position: what every team allows to opposing guards, forwards and centers."""
import numpy as np
import pandas as pd

from src.load import POSITIONS, UNKNOWN

STATS = ["pts", "pir", "reb", "ast", "fg3m"]
EXPECTED = ["pts", "pir"]   # stats that also get an opponent-adjusted version
SHRINK_MINUTES = 40.0       # how many minutes of the position average a player's rate starts from


def add_expected(games: pd.DataFrame) -> pd.DataFrame:
    """Expected pts and PIR for every player-game, from his OTHER games this season.

    rate = (stat in other games + 40 min x position rate) / (minutes in other games + 40)
    expected = rate x minutes in this game

    Leaving the game itself out is what keeps the measure honest: a player's big
    night against a weak defense must not raise his own expectation for that night.
    """
    g = games[games["minutes"] > 0].copy()
    totals = g.groupby("player_id")[EXPECTED + ["minutes"]].transform("sum")
    for stat in EXPECTED:
        pos_rate = g.groupby("position")[stat].transform("sum") / g.groupby("position")["minutes"].transform("sum")
        other_stat = totals[stat] - g[stat]
        other_min = totals["minutes"] - g["minutes"]
        rate = (other_stat + SHRINK_MINUTES * pos_rate) / (other_min + SHRINK_MINUTES)
        g[f"{stat}_exp"] = rate * g["minutes"]
    return g


def by_game(games: pd.DataFrame) -> pd.DataFrame:
    """One row per game x defending team x opposing position."""
    g = add_expected(games)
    agg = {s: (s, "sum") for s in STATS}
    agg.update({f"{s}_exp": (f"{s}_exp", "sum") for s in EXPECTED})
    agg.update(minutes=("minutes", "sum"), players=("player_id", "nunique"))
    out = (
        g.groupby(["season", "phase", "round", "game_code", "opponent", "team", "home", "position"])
         .agg(**agg)
         .reset_index()
         # `opponent` of the scoring players is the defending team
         .rename(columns={"opponent": "defense", "team": "offense", "home": "offense_home"})
    )
    out["defense_home"] = 1 - out["offense_home"]
    return out.drop(columns="offense_home")


def summarize(games_by_pos: pd.DataFrame, last_n: int | None = None) -> pd.DataFrame:
    """Season table: one row per defending team and position (Unknown left out)."""
    d = games_by_pos[games_by_pos["position"].isin(POSITIONS)].copy()
    if last_n:
        recent = (d[["defense", "game_code"]].drop_duplicates()
                    .sort_values("game_code").groupby("defense").tail(last_n))
        d = d.merge(recent, on=["defense", "game_code"])

    # a position with no player in a game still counts as a game with 0 allowed
    games_per_team = d.groupby("defense")["game_code"].nunique().rename("games")
    sums = d.groupby(["defense", "position"])[STATS + [f"{s}_exp" for s in EXPECTED] + ["minutes"]].sum()
    t = sums.reset_index().merge(games_per_team.reset_index(), on="defense")

    for s in STATS:
        t[f"{s}_allowed"] = t[s] / t["games"]
    t["pts_per40"] = np.where(t["minutes"] > 0, t["pts"] / t["minutes"] * 40, np.nan)
    for s in EXPECTED:
        t[f"{s}_over_expected"] = (t[s] - t[f"{s}_exp"]) / t["games"]

    league = t.groupby("position")["pts_allowed"].transform("mean")
    t["pts_index"] = t["pts_allowed"] / league
    # 1 = weakest defense against that position (allows the most over expectation)
    t["rank"] = t.groupby("position")["pts_over_expected"].rank(ascending=False, method="min").astype(int)

    cols = ["defense", "position", "games", "pts_allowed", "pts_index", "pts_per40",
            "pts_over_expected", "rank", "pir_allowed", "pir_over_expected",
            "reb_allowed", "ast_allowed", "fg3m_allowed"]
    order = {p: i for i, p in enumerate(POSITIONS)}
    t = t[cols].sort_values(["position", "rank"], key=lambda s: s.map(order) if s.name == "position" else s)
    return t.reset_index(drop=True).round(2)


WINDOWS = [3, 5, 10]
POS_LABEL = {"Guard": "guard", "Forward": "forward", "Center": "center"}


def recent_form(games_by_pos: pd.DataFrame, windows: list[int] = WINDOWS) -> pd.DataFrame:
    """One row per team: points allowed per game to each position over its last N games.

    The last column says which position the team is weakest against. Raw points
    can't decide that (guards always score the most), so each figure is compared
    with the league average for that position over the same window, and the
    position with the highest average ratio over all windows wins.
    """
    d = games_by_pos[games_by_pos["position"].isin(POSITIONS)]
    team_games = (d[["defense", "game_code"]].drop_duplicates()
                    .sort_values("game_code", ascending=False))
    pts = (d.pivot_table(index=["defense", "game_code"], columns="position",
                         values="pts", aggfunc="sum", fill_value=0)
             .reindex(columns=POSITIONS, fill_value=0).reset_index())

    out = team_games.groupby("defense").size().rename("games").to_frame()
    ratios = {p: [] for p in POSITIONS}
    for n in windows:
        last = team_games.groupby("defense").head(n)
        window = pts.merge(last, on=["defense", "game_code"]).groupby("defense")[POSITIONS].mean()
        league = window.mean()
        for p in POSITIONS:
            out[f"{POS_LABEL[p]}_last{n}"] = window[p]
            ratios[p].append(window[p] / league[p])

    index = pd.DataFrame({p: sum(r) / len(r) for p, r in ratios.items()})
    out["weakest_vs"] = index.idxmax(axis=1)
    out["weakest_vs_pct"] = (index.max(axis=1) - 1) * 100   # % above the league average
    out = out.reset_index().sort_values("weakest_vs_pct", ascending=False)
    return out.round(1).reset_index(drop=True)


def check(games: pd.DataFrame, games_by_pos: pd.DataFrame) -> list[str]:
    """Accuracy checks; an empty list means everything adds up."""
    problems = []
    per_game = games.groupby("game_code")["team"].nunique()
    if (per_game != 2).any():
        problems.append(f"games without exactly 2 teams: {per_game[per_game != 2].index.tolist()}")

    # points allowed over all positions (Unknown included) = the opponent's final score
    allowed = (games_by_pos.groupby(["game_code", "defense"])["pts"].sum()
                           .rename("allowed").reset_index())
    score = (games.drop_duplicates(["game_code", "team"])[["game_code", "team", "opp_score"]]
                  .rename(columns={"team": "defense"}))
    both = score.merge(allowed, on=["game_code", "defense"], how="left").fillna({"allowed": 0})
    wrong = both[both["allowed"] != both["opp_score"]]
    if not wrong.empty:
        problems.append(f"points by position do not add up to the final score in {len(wrong)} team-games")

    played = games[games["minutes"] > 0]
    known = played.loc[played["position"] != UNKNOWN, "minutes"].sum() / played["minutes"].sum()
    if known < 0.99:
        problems.append(f"only {known:.1%} of minutes have a position")
    return problems
