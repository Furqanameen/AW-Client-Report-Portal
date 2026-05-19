import os
from pathlib import Path

from flask import Flask

from app.database import init_db
from app.routes import api_bp, web_bp


def _database_path() -> str:
    if path := os.environ.get("DATABASE_PATH"):
        return path
    if path := os.environ.get("RAILWAY_DATABASE_PATH"):
        return path
    if os.environ.get("VERCEL"):
        return "/tmp/portal.db"
    return str(Path(__file__).parent.parent / "data" / "portal.db")


def create_app():
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent.parent / "templates"),
        static_folder=str(Path(__file__).parent.parent / "static"),
    )
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    app.config["DATABASE_PATH"] = _database_path()

    init_db(app)
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
