from __future__ import annotations

import io
import os
import time
from pathlib import Path

import pandas as pd
import requests
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from rankings_engine import rank_weekly, latest_completed_week, POSITIONS


app = FastAPI(
    title="NFL Offensive Rankings API",
    version="1.0",
)


DATA_URL = os.getenv(
    "NFLVERSE_URL",
    "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.csv",
)

CACHE = Path(os.getenv("NFL_CACHE", "nfl_cache.csv"))


def load_data():
    if CACHE.exists() and time.time() - CACHE.stat().st_mtime < 900:
        return pd.read_csv(CACHE)

    r = requests.get(DATA_URL, timeout=60)
    r.raise_for_status()

    CACHE.write_bytes(r.content)

    return pd.read_csv(io.BytesIO(r.content))


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
        <body>
            <h1>NFL Offensive Rankings API</h1>
            <p>Use /api/rankings?position=QB&view=season</p>
        </body>
    </html>
    """


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "source": DATA_URL,
        "cache": CACHE.exists(),
    }


@app.get("/api/rankings")
def rankings(
    position: str = Query("QB", pattern="^(QB|RB|WR|TE)$"),
    view: str = Query("season", pattern="^(season|week|last3|ppr)$"),
):
    df = load_data()

    # Only use the current NFL season.
    if "season" in df.columns:
        df = df[
            pd.to_numeric(df["season"], errors="coerce") == 2026
        ]

    # Regular season only.
    if "season_type" in df.columns:
        df = df[
            df["season_type"]
            .astype(str)
            .str.lower()
            .isin(["reg", "regular"])
        ]

    if view == "week":
        df, week = latest_completed_week(df)

    elif view == "last3":
        weeks = sorted(
            pd.to_numeric(
                df["week"], errors="coerce"
            )
            .dropna()
            .unique()
        )

        if weeks:
            df = df[df["week"].isin(weeks[-3:])]
            week = weeks[-3:]
        else:
            week = []

    else:
        week = None

    ranked = rank_weekly(df, position)

    if view == "ppr":
        ranked = (
            ranked
            .sort_values("ppr", ascending=False)
            .head(10)
            .copy()
        )
    else:
        ranked = (
            ranked
            .sort_values("performance_score", ascending=False)
            .head(10)
            .copy()
        )

    ranked["rank"] = range(1, len(ranked) + 1)

    return {
        "position": position,
        "view": view,
        "week": week,
        "updated_at": int(time.time()),
        "players": ranked.fillna("").to_dict(orient="records"),
    }


@app.get("/api/all")
def all_rankings(
    view: str = Query(
        "season",
        pattern="^(season|week|last3|ppr)$",
    )
):
    return {
        position: rankings(position, view)
        for position in POSITIONS
    }


# ---------------------------------------------------------------------------
# Game-by-game snapshot support
# ---------------------------------------------------------------------------

ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
)
ESPN_SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
)


def _espn_json(url, params=None):
    response = requests.get(
        url,
        params=params,
        timeout=30,
        headers={"User-Agent": "NFL-Offensive-Rankings/1.0"},
    )
    response.raise_for_status()
    return response.json()


def completed_games(date=None):
    """Return completed regular-season games for a date from ESPN."""
    params = {"dates": date} if date else {}
    data = _espn_json(ESPN_SCOREBOARD_URL, params=params)

    games = []
    for event in data.get("events", []):
        competition = (event.get("competitions") or [{}])[0]
        status = competition.get("status", {}).get("type", {})
        if status.get("completed") and event.get("season", {}).get("type") == 2:
            games.append({
                "game_id": event.get("id"),
                "date": event.get("date"),
                "name": event.get("name"),
                "status": status.get("description"),
            })
    return games


@app.get("/api/games")
def games(date: str | None = None):
    """List completed regular-season games, optionally for YYYYMMDD."""
    return {"games": completed_games(date)}


@app.get("/api/snapshot")
def snapshot(
    game_id: str,
    position: str = Query("QB", pattern="^(QB|RB|WR|TE)$"),
):
    """
    Return a game-aware ranking snapshot.

    The weekly nflverse feed remains the authoritative season/statistics source.
    ESPN supplies the completed-game identifier so the UI can display and track
    the sequence of completed games.
    """
    data = _espn_json(ESPN_SUMMARY_URL, {"event": game_id})

    competition = (data.get("header", {}).get("competitions") or [{}])[0]
    status = competition.get("status", {}).get("type", {})

    if not status.get("completed"):
        return {
            "game_id": game_id,
            "completed": False,
            "players": [],
        }

    # The current rankings endpoint contains the complete current-season
    # ranking. The game ID is attached so the frontend can record the snapshot.
    result = rankings(position=position, view="season")
    result["game_id"] = game_id
    result["completed"] = True
    return result
