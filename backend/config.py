import os

try:
    from dotenv import load_dotenv

    load_dotenv()  # reads backend/.env into os.environ, if present
except ImportError:
    # python-dotenv not installed - COMFYUI_URL / GROQ_API_KEY etc. will
    # only pick up values from real environment variables, not .env.
    # `pip install python-dotenv` to enable .env file support.
    pass


class Config:
    # Falls back to a local sqlite file so the app runs out of the box
    # without anyone having to spin up postgres first. Set DATABASE_URL
    # to a real postgres connection string for the graded/hosted version.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///content_engine.db"
    )
    # Render/Heroku-style urls sometimes come as postgres:// which
    # sqlalchemy 1.4+ no longer accepts directly.
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql://", 1
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

    # Optional: only needed if you actually wire up a live ComfyUI instance
    # for the assignment-2 brownie points. Leave blank to skip that path.
    COMFYUI_URL = os.environ.get("COMFYUI_URL", "")

    STATIC_GENERATED_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "static", "generated"
    )
    STATIC_UPLOADS_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "static", "uploads"
    )
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
