import pandas as pd
import pytest

from src.dvp import add_expected, by_game, check, summarize


def make_games() -> pd.DataFrame:
    """Two games, A vs B and A vs C, with one guard, forward and center per team."""
    rows = []

    def team(game, rnd, team, opp, home, pts, opp_pts, players):
        for pid, pos, p, mins in players:
            rows.append(dict(season=2026, phase="RS", round=rnd, game_code=game,
                             player_id=pid, team=team, opponent=opp, home=home,
                             position=pos, minutes=mins, pts=p, pir=p, reb=1, ast=1,
                             fg3m=0, team_score=pts, opp_score=opp_pts))

    team(1, 1, "A", "B", 1, 30, 25, [("a1", "Guard", 20, 30), ("a2", "Forward", 6, 30), ("a3", "Center", 4, 30)])
    team(1, 1, "B", "A", 0, 25, 30, [("b1", "Guard", 15, 30), ("b2", "Forward", 5, 30), ("b3", "Center", 5, 30)])
    team(2, 2, "A", "C", 0, 22, 18, [("a1", "Guard", 10, 30), ("a2", "Forward", 8, 30), ("a3", "Center", 4, 30)])
    team(2, 2, "C", "A", 1, 18, 22, [("c1", "Guard", 9, 30), ("c2", "Forward", 6, 30), ("c3", "Center", 3, 30)])
    return pd.DataFrame(rows)


def test_positions_add_up_to_final_score():
    games = make_games()
    assert check(games, by_game(games)) == []


def test_check_catches_missing_points():
    games = make_games()
    per_game = by_game(games)
    per_game.loc[0, "pts"] += 1
    assert any("final score" in p for p in check(games, per_game))


def test_defense_is_the_opponent_of_the_scorers():
    per_game = by_game(make_games())
    row = per_game[(per_game.game_code == 1) & (per_game.defense == "B") & (per_game.position == "Guard")]
    assert row["pts"].item() == 20          # A's guard scored 20 against B
    assert row["offense"].item() == "A"


def test_expected_leaves_out_the_game_itself():
    g = add_expected(make_games())
    # a1: 20 pts in game 1, 10 in game 2. In game 1 his expectation must come from game 2 only
    # (shrunk towards the guard average), so it is well below the 20 he actually scored.
    a1_g1 = g[(g.player_id == "a1") & (g.game_code == 1)]["pts_exp"].item()
    assert a1_g1 < 15


def test_summary_ranks_weakest_defense_first():
    t = summarize(by_game(make_games()))
    guards = t[t.position == "Guard"]
    assert guards.iloc[0]["rank"] == 1
    assert guards["pts_over_expected"].is_monotonic_decreasing
    assert set(guards.defense) == {"A", "B", "C"}
    assert guards.set_index("defense").loc["A", "games"] == 2


def test_position_coverage_is_checked():
    games = make_games()
    games["position"] = "Unknown"
    assert any("position" in p for p in check(games, by_game(games)))


def test_recent_form_uses_latest_games():
    from src.dvp import recent_form
    per_game = by_game(make_games())
    form = recent_form(per_game, windows=[1, 2]).set_index("defense")
    # A's latest game is game 2 (vs C): C's guard scored 9 there, B's guard 15 in game 1
    assert form.loc["A", "guard_last1"] == 9
    assert form.loc["A", "guard_last2"] == 12


def test_weakest_position_is_relative_to_league_average():
    from src.dvp import recent_form
    games = make_games()
    # B's defense now gives A's center 12 instead of 4: a lot for a center, few points in total
    games.loc[(games.game_code == 1) & (games.player_id == "a3"), "pts"] = 12
    games.loc[(games.game_code == 1) & (games.team == "A"), "team_score"] = 38
    games.loc[(games.game_code == 1) & (games.team == "B"), "opp_score"] = 38
    form = recent_form(by_game(games), windows=[1]).set_index("defense")
    assert form.loc["B", "guard_last1"] > form.loc["B", "center_last1"]   # guards still score more...
    assert form.loc["B", "weakest_vs"] == "Center"                         # ...but centers are the weak spot
