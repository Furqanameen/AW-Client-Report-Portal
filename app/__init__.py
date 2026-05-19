import os
from pathlib import Path

from flask import Flask

from app.database import init_db
from app.routes import api_bp, web_bp


def _is_serverless() -> bool:
    return bool(
        os.environ.get("VERCEL")
        or os.environ.get("VERCEL_ENV")
        or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        or os.environ.get("LAMBDA_TASK_ROOT")
    )


def _database_path() -> str:
    if path := os.environ.get("DATABASE_PATH"):
        return path
    if path := os.environ.get("RAILWAY_DATABASE_PATH"):
        return path
    if _is_serverless():
        return "/tmp/portal.db"

    local_path = Path(__file__).parent.parent / "data" / "portal.db"
    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        probe = local_path.parent / ".write_probe"
        probe.write_text("1", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return str(local_path)
    except OSError:
        return "/tmp/portal.db"


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
