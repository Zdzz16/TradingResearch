"""
TradingResearch dashboard — our own web app (Flask).

Deliberately blank for now: it serves one dark page and nothing else. The
UI is designed together before anything goes on it. No third-party UI
framework and no chrome — every pixel here is ours. Later this same server
grows an API endpoint that calls run_strategy() and returns JSON, and the
page's own JavaScript renders the results.

Run:  python3 dashboard/app.py      then open http://127.0.0.1:8501
"""

from flask import Flask

app = Flask(__name__)

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TradingResearch</title>
  <style>
    :root { color-scheme: dark; }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      background: #0e1117;
      color: #e6e6e6;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
  </style>
</head>
<body>
  <!-- Intentionally empty — UI to be designed together. -->
</body>
</html>
"""


@app.route("/")
def index():
    return PAGE


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8501, debug=False)
