from flask import Flask
import os

app = Flask(__name__)


@app.route("/")
def hello_world():
    # Demonstrates that it's our custom app and can read env vars
    hostname = os.environ.get("HOSTNAME", "unknown")
    return f"Hello from our Custom Flask App, running on pod: {hostname}!"


if __name__ == "__main__":
    # Listen on all network interfaces, essential for Docker
    app.run(host="0.0.0.0", port=5000)
