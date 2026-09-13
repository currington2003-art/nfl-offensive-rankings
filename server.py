from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import urlopen
import json, csv, io, os

# nflverse publishes release files through GitHub. The app uses the CSV release
# so it can run without an R installation.
DATA_URL = "https://github.com/nflverse/nflverse-data/releases/download/player_stats/player_stats.csv"

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, content_type="application/json"):
        raw = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/api/health":
            return self._send(200, json.dumps({"ok": True, "source": DATA_URL}))
        if self.path.startswith("/api/rankings"):
            # This starter backend is intentionally thin. It verifies that the
            # production data endpoint is reachable; ranking aggregation lives
            # in the browser until a deployment database is added.
            try:
                with urlopen(DATA_URL, timeout=20) as r:
                    data = r.read()
                return self._send(200, json.dumps({
                    "ok": True,
                    "source": DATA_URL,
                    "bytes": len(data),
                    "message": "NFL data source reachable. Connect this payload to the ranking engine."
                }))
            except Exception as e:
                return self._send(502, json.dumps({"ok": False, "error": str(e)}))
        return self._send(200, "<h1>NFL Offensive Rankings API</h1>", "text/html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"NFL Offensive Rankings running at http://localhost:{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
