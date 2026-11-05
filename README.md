# EuroLeague Defense vs Position

![Update](https://github.com/straledev/euroleague-defense-vs-position/actions/workflows/update.yml/badge.svg)

How many points every EuroLeague team allows to opposing **guards, forwards and centers**, game by game and adjusted for the strength of the players it faced. Updated every day.

**Live dashboard:** [your-app.streamlit.app](https://your-app.streamlit.app)

Built on [euroleague-fantasy-data](https://github.com/straledev/euroleague-fantasy-data), which provides verified box scores and EuroLeague Fantasy positions.

## The tables

| File | One row = |
|---|---|
| [`output/dvp_recent_2026-27.csv`](output/dvp_recent_2026-27.csv) | One team: points allowed to guards, forwards and centers over its last 3, 5 and 10 games, and the position it is weakest against |
| [`output/dvp_2026-27.csv`](output/dvp_2026-27.csv) | One defending team and one position, whole season |
| [`output/dvp_by_game_2026-27.csv`](output/dvp_by_game_2026-27.csv) | One game, one defending team, one position (for filters such as last 5 games or home/away) |
| [`output/meta.json`](output/meta.json) | Games included, last complete round, when the data was updated |

### Recent form: `dvp_recent_2026-27.csv`

| Column | Meaning |
|---|---|
| `guard_last3`, `guard_last5`, `guard_last10` | Points per game scored against this team by opposing guards in its last 3, 5 and 10 games (same for `forward_` and `center_`) |
| `weakest_vs` | The position this team is weakest against |
| `weakest_vs_pct` | How far above the league average (in %) the team allows that position |

Raw points can't tell which position a team is weakest against, because guards always score the most (about 42 points a game, against 30 for forwards and 15 for centers). So every figure is compared with the league average for the same position and window, the three windows are averaged, and the position with the highest ratio wins. A team that allows centers 20 points (33% above average) is weaker against centers than against guards at 46 points (10% above). Early in the season `last10` covers all games played so far.

### Season table: `dvp_2026-27.csv`

Main columns:

| Column | Meaning |
|---|---|
| `pts_allowed` | Points per game scored against this team by players of that position |
| `pts_index` | `pts_allowed` relative to the league average for the position (1.15 = 15% more) |
| `pts_per40` | Points per 40 minutes played by that position, which corrects for overtime and rotations |
| `pts_over_expected` | Points per game above (+) or below (−) what the same players usually score in those minutes |
| `rank` | 1 = weakest defense against that position, by `pts_over_expected` |
| `pir_allowed`, `pir_over_expected` | The same for PIR |
| `reb_allowed`, `ast_allowed`, `fg3m_allowed` | Rebounds, assists and made threes allowed per game |

## Method

1. Every player in every game gets his **EuroLeague Fantasy position** (Guard, Forward, Center) from the dataset's player map.
2. For each game, the points of all opposing players of one position are added up. That is what the defense allowed to that position in that game.
3. The season figure is the average over the team's games.
4. **Opponent adjustment.** A team that faced strong guards would look like a weak defense on raw numbers alone. So each player also gets an *expected* score: his points per minute in his **other** games this season, times his minutes in this game. Players with few minutes are pulled towards the average for their position (40 minutes of the position average are added to their sample). `pts_over_expected` is the actual total minus the expected total, per game.

## Accuracy checks

The tables are only saved when every check passes:

- **Positions add up to the score.** In every game, the points allowed to guards, forwards, centers (and players without a position) add up exactly to the opponent's final score.
- Every game has exactly two teams.
- At least 99% of minutes played have a position.

The underlying dataset verifies every game against the official final score before publishing it. Unit tests for the calculations are in [`tests/`](tests/).

## Limitations

- **Small samples.** After 10 rounds each team has about 10 games, so differences of 2–3 points can still be noise. The `games` column shows the sample.
- **Three broad positions.** The fantasy game's positions are used on purpose, because they match how fantasy teams are picked, but "forward" covers very different players.
- The expected score uses only the current season, so early-season adjustments are rough.

## Run it

```bash
pip install -r requirements.txt
python -m pytest
python -m src.build --season 2026-27
```

Dashboard:

```bash
pip install streamlit
streamlit run app/streamlit_app.py
```

The data is read straight from GitHub. To use a local clone of the dataset instead, set `EL_DATA_DIR` to its `data` folder.

## Using the tables

```python
import pandas as pd

url = "https://raw.githubusercontent.com/straledev/euroleague-defense-vs-position/main/output/dvp_2026-27.csv"
dvp = pd.read_csv(url)
print(dvp[dvp.position == "Guard"].head(5)[["team_name", "pts_allowed", "pts_over_expected", "rank"]])
```

## License

[MIT](LICENSE)