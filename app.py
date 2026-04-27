"""
Simple keep-alive server for Render.
The REAL bot runs in a SEPARATE process via bot.py.
This just keeps the Render web service alive for UptimeRobot pings.
"""
from flask import Flask
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Token Bot Running (Polling Mode)"

@app.route("/health")
def health():
    return {"status": "ok", "mode": "polling"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True)
