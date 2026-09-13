# NFL Offensive Rankings

## Current build

This is the mobile-first web prototype plus a Python backend scaffold.

### Positions
- QB
- RB
- WR
- TE

Offensive line is excluded.

### Data source

The production data layer is designed around nflverse. nflverse publishes player statistics through GitHub releases and provides weekly player stats with position, team, passing, rushing and receiving fields.

The project deliberately keeps the data source separate from the ranking algorithm so the scoring model can be changed without redesigning the application.

## Run locally

Python 3.10+:

```bash
python server.py
```

Then open:

`http://localhost:8000`

## Production next step

Deploy the backend and replace the browser demo array with a server-side aggregation pipeline:

1. Pull the current season player-stat release.
2. Keep only regular-season completed weeks.
3. Join roster/position data.
4. Aggregate season, latest-week, and rolling-three-game totals.
5. Calculate separate position-specific performance scores.
6. Calculate PPR fantasy scores.
7. Store a snapshot after each completed game.
8. Serve `/api/rankings` to the web UI.

nflverse data is updated automatically, so this architecture supports the requested post-game updates.
