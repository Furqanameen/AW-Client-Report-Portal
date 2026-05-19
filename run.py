"""Local development server. Vercel uses wsgi.py (see pyproject.toml)."""
import os

from wsgi import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
