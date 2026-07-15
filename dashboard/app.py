"""
TradingResearch dashboard — our own web app (Flask).

No third-party UI framework and no chrome — every pixel is ours. The page
itself lives in templates/index.html; this file just serves it. Later this
same server grows a JSON API that calls run_strategy(), and the page's own
JavaScript renders the results.

Run:  python3 dashboard/app.py      then open http://127.0.0.1:8501
"""

from flask import Flask, render_template

app = Flask(__name__)

# Pick up edits to templates/ on the next browser refresh, so iterating on
# the UI doesn't need a server restart.
app.jinja_env.auto_reload = True
app.config["TEMPLATES_AUTO_RELOAD"] = True


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8501, debug=False)
