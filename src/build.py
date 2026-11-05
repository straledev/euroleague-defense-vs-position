"""Builds the defense-vs-position tables and saves them in output/."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.dvp import by_game, check, recent_form, summarize
from src.load import load_games, load_status

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"

TEAM_NAMES = {
    "ASV": "LDLC ASVEL", "BAR": "FC Barcelona", "BAS": "Baskonia", "BES": "Beşiktaş",
    "DUB": "Dubai Basketball", "HTA": "Hapoel Tel Aviv", "IST": "Anadolu Efes",
    "MAD": "Real Madrid", "MIL": "Olimpia Milano", "MUN": "Bayern München",
    "OLY": "Olympiacos", "PAM": "Valencia Basket", "PAN": "Panathinaikos",
    "PAR": "Partizan", "PRS": "Paris Basketball", "RED": "Crvena zvezda",
    "TEL": "Maccabi Tel Aviv", "ULK": "Fenerbahçe", "VIR": "Virtus Bologna",
    "ZAL": "Žalgiris",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="2026-27")
    args = ap.parse_args()

    games = load_games(args.season)
    status = load_status(args.season)
    per_game = by_game(games)

    problems = check(games, per_game)
    if problems:
        print("Provera nije prosla, rezultati se ne cuvaju:")
        for p in problems:
            print("  -", p)
        sys.exit(1)

    table = summarize(per_game)
    table.insert(1, "team_name", table["defense"].map(TEAM_NAMES).fillna(table["defense"]))

    form = recent_form(per_game)
    form.insert(1, "team_name", form["defense"].map(TEAM_NAMES).fillna(form["defense"]))

    OUT.mkdir(exist_ok=True)
    form.to_csv(OUT / f"dvp_recent_{args.season}.csv", index=False)
    table.to_csv(OUT / f"dvp_{args.season}.csv", index=False)
    per_game.round(2).to_csv(OUT / f"dvp_by_game_{args.season}.csv", index=False)
    complete = [r for r in status.get("rounds_complete", []) if isinstance(r, int)]
    last_full = max(complete) if complete else 0
    meta = {
        "season": args.season,
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "games": int(games["game_code"].nunique()),
        "last_complete_round": last_full,
        "games_after_last_complete_round": int(
            games.loc[(games["phase"] == "RS") & (games["round"] > last_full), "game_code"].nunique()),
        "data_updated_utc": status.get("updated_utc"),
        "team_names": TEAM_NAMES,
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    extra = meta["games_after_last_complete_round"]
    print(f"Sezona {args.season}: {meta['games']} utakmica (kola 1-{last_full}"
          f"{f' + {extra} iz sledeceg kola' if extra else ''}). Sve provere prosle.")
    cols = ["team_name", "games"] + [c for c in form.columns if "_last" in c] + ["weakest_vs", "weakest_vs_pct"]
    print(form[cols].to_string(index=False))


if __name__ == "__main__":
    main()
