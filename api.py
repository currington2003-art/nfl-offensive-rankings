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
