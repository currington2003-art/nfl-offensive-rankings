"""
NFL Offensive Rankings — production ranking engine.

Data source:
nflverse weekly regular-season player stats.
The engine intentionally excludes OL and special teams and ranks QB/RB/WR/TE.

The scoring model is transparent and easy to tune.
"""

from __future__ import annotations
import math
import pandas as pd

POSITIONS = ("QB", "RB", "WR", "TE")

def _n(df, col):
    return pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0)

def add_ppr(df):
    # Standard PPR: 1/reception, 0.1 receiving/rushing yard, 6 TD,
    # -2 interception, -2 lost fumble. Passing: 0.04/yd, 4 TD, -2 INT.
    return (
        _n(df,"receptions") +
        0.1*_n(df,"receiving_yards") +
        0.1*_n(df,"rushing_yards") +
        6*(_n(df,"receiving_tds")+_n(df,"rushing_tds")) +
        0.04*_n(df,"passing_yards") +
        4*_n(df,"passing_tds") -
        2*_n(df,"interceptions") -
        2*_n(df,"rushing_fumbles_lost") -
        2*_n(df,"receiving_fumbles_lost")
    )

def position_score(row, pos):
    # Position-specific "how well did he play?" score.
    if pos == "QB":
        return (
            0.035*row.pass_yards +
            4.0*row.pass_tds -
            4.5*row.interceptions +
            0.08*row.rush_yards +
            5.0*row.rush_tds +
            0.35*row.completions +
            0.02*row.pass_epa
        )
    if pos == "RB":
        return (
            0.16*row.rush_yards +
            5.5*row.rush_tds +
            0.10*row.rec_yards +
            1.2*row.receptions +
            4.0*row.rec_tds +
            0.05*row.rush_epa
        )
    if pos in ("WR","TE"):
        return (
            0.13*row.rec_yards +
            1.5*row.receptions +
            6.0*row.rec_tds +
            0.05*row.rec_epa
        )
    return 0

def normalize_columns(df):
    aliases = {
        "passing_yards":"pass_yards",
        "passing_tds":"pass_tds",
        "rushing_yards":"rush_yards",
        "rushing_tds":"rush_tds",
        "receiving_yards":"rec_yards",
        "receiving_tds":"rec_tds",
        "fantasy_points_ppr":"ppr",
    }
    for src,dst in aliases.items():
        if src in df.columns and dst not in df.columns:
            df[dst] = df[src]
    numeric = [
        "pass_yards","pass_tds","interceptions","rush_yards","rush_tds",
        "rec_yards","rec_tds","receptions","completions","pass_epa",
        "rush_epa","rec_epa","rushing_fumbles_lost","receiving_fumbles_lost"
    ]
    for c in numeric:
        if c not in df.columns: df[c] = 0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df

def rank_weekly(df, position=None):
    df = normalize_columns(df.copy())
    df = df[df["position"].isin(POSITIONS)].copy()
    if position:
        df = df[df.position == position].copy()

    df["ppr"] = add_ppr(df)
    df["performance_score_raw"] = [
        position_score(r, r.position) for _, r in df.iterrows()
    ]

    group_cols = ["player_id","player_name","position"]
    if "team" in df.columns: group_cols.append("team")

    out = df.groupby(group_cols, dropna=False).agg(
        ppr=("ppr","sum"),
        performance_score=("performance_score_raw","sum"),
        pass_yards=("pass_yards","sum"),
        pass_tds=("pass_tds","sum"),
        interceptions=("interceptions","sum"),
        rush_yards=("rush_yards","sum"),
        rush_tds=("rush_tds","sum"),
        rec_yards=("rec_yards","sum"),
        rec_tds=("rec_tds","sum"),
        receptions=("receptions","sum"),
    ).reset_index()

    out["rank"] = out.groupby("position")["performance_score"].rank(
        ascending=False, method="first"
    ).astype(int)
    return out.sort_values(["position","rank"])

def latest_completed_week(df):
    if "week" not in df.columns:
        return df, None
    weeks = pd.to_numeric(df.week, errors="coerce").dropna()
    if weeks.empty:
        return df, None
    w = int(weeks.max())
    return df[df.week == w], w
