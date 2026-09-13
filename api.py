from __future__ import annotations
import os, io, json, sqlite3, time
from pathlib import Path
import pandas as pd
import requests
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from rankings_engine import rank_weekly, latest_completed_week, POSITIONS

app = FastAPI(title="NFL Offensive Rankings API", version="1.0")

# nflverse's public release naming is maintained by the nflverse project.
# The current 2026 regular-season player-stat release exists; the URL can be
# changed here if the release format changes.
DATA_URL = os.getenv(
    "NFLVERSE_URL",
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "stats_player_reg_2026/stats_player_reg_2026.parquet"
)

CACHE = Path(os.getenv("NFL_CACHE","nfl_cache.parquet"))

def load_data():
    if CACHE.exists() and time.time()-CACHE.stat().st_mtime < 900:
        return pd.read_parquet(CACHE)
    r = requests.get(DATA_URL, timeout=30)
    r.raise_for_status()
    CACHE.write_bytes(r.content)
    return pd.read_parquet(io.BytesIO(r.content))

@app.get("/", response_class=HTMLResponse)
def home():
    return """<html><body><h1>NFL Offensive Rankings API</h1>
    <p>Use /api/rankings?position=QB&view=season</p></body></html>"""

@app.get("/api/health")
def health():
    return {"ok": True, "source": DATA_URL, "cache": CACHE.exists()}

@app.get("/api/rankings")
def rankings(
    position: str = Query("QB", pattern="^(QB|RB|WR|TE)$"),
    view: str = Query("season", pattern="^(season|week|last3|ppr)$")
):
    df = load_data()

# Only use the current NFL season.
if "season" in df.columns:
    df = df[pd.to_numeric(df["season"], errors="coerce") == 2026]

# Regular season only.
if "season_type" in df:
    df = df[df.season_type.astype(str).str.lower().isin(["reg", "regular"])]
    if view == "week":
        df, week = latest_completed_week(df)
    elif view == "last3":
        weeks = sorted(pd.to_numeric(df.week, errors="coerce").dropna().unique())
        df = df[df.week.isin(weeks[-3:])] if weeks else df
        week = weeks[-3:] if weeks else []
    else:
        week = None

    ranked = rank_weekly(df, position)
    if view == "ppr":
        ranked = ranked.sort_values("ppr", ascending=False).head(10).copy()
    else:
        ranked = ranked.sort_values("performance_score", ascending=False).head(10).copy()

    ranked["rank"] = range(1, len(ranked)+1)
    return {
        "position": position,
        "view": view,
        "week": week,
        "updated_at": int(time.time()),
        "players": ranked.fillna("").to_dict(orient="records")
    }

@app.get("/api/all")
def all_rankings(view: str = "season"):
    return {p: rankings(p, view) for p in POSITIONS}
