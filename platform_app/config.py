import os


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "app.db")
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    STORAGE_DIR = os.environ.get(
        "STORAGE_DIR",
        os.path.join(BASE_DIR, "storage")
    )

    BASE_PUBLIC_URL = os.environ.get(
        "BASE_PUBLIC_URL",
        "http://127.0.0.1:5000"
    )