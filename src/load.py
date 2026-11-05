"""Loads the EuroLeague Fantasy dataset (box scores + fantasy positions).

By default the data is read straight from GitHub. Set the environment variable
EL_DATA_DIR to a local clone's `data` folder to work offline.
"""
import json
import os
from urllib.request import urlopen

import pandas as pd

REMOTE = "https://raw.githubusercontent.com/straledev/euroleague-fantasy-data/main/data"
POSITIONS = ["Guard", "Forward", "Center"]
UNKNOWN = "Unknown"


def _base() -> str:
    return os.environ.get("EL_DATA_DIR", REMOTE).rstrip("/")


def _path(season: str, name: str) -> str:
    return f"{_base()}/{season}/{name}"


def load_games(season: str) -> pd.DataFrame:
    """One row per player per game, with the player's fantasy position."""
    games = pd.read_csv(_path(season, "rounds/merged_rounds.csv"), dtype={"player_id": str})
    pmap = pd.read_csv(_path(season, "player_map.csv"), dtype={"player_id": str})

    games = games.merge(pmap[["player_id", "team", "position"]],
                        on=["player_id", "team"], how="left")
    games["position"] = games["position"].fillna(UNKNOWN)
    return games


def load_status(season: str) -> dict:
    """The dataset's own completeness report (collection_status.json)."""
    path = _path(season, "collection_status.json")
    if path.startswith("http"):
        with urlopen(path, timeout=30) as r:
            return json.load(r)
    with open(path, encoding="utf-8") as f:
        return json.load(f)
