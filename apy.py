"""Punto de entrada de desarrollo para la aplicación oficial FitPath 2.0."""

from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

from backend.fitpath import create_app  # noqa: E402


app = create_app("development")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
