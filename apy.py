import os
from pathlib import Path

from flask import Flask, render_template, redirect, url_for, session, jsonify
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="statics",
    static_url_path="/statics"
)

app.secret_key = os.getenv("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("Falta FLASK_SECRET_KEY en el archivo .env")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False  # Solo para localhost
)

# Configuración de Google OAuth
oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"}
)


# Vistas
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/inicio")
def inicio():
    return render_template("inicio.html")


@app.route("/perfil")
def perfil():
    if "usuario" not in session:
        return redirect(url_for("index"))
    return render_template("perfil.html")


@app.route("/buscador")
def buscador():
    return render_template("buscador.html")


# Inicio de sesión con Google
@app.route("/auth/google")
def login_google():
    callback = url_for("google_callback", _external=True)
    return google.authorize_redirect(callback)


# Respuesta de Google
@app.route("/auth/google/callback")
def google_callback():
    token = google.authorize_access_token()
    datos = token["userinfo"]

    if not datos.get("sub") or not datos.get("email_verified"):
        return "No se pudo verificar la cuenta de Google", 403

    session.clear()
    session["usuario"] = {
        "google_id": datos["sub"],
        "nombre": datos.get("name", ""),
        "email": datos.get("email", "")
    }

    return redirect(url_for("estado_auth"))


# Comprobar autenticación
@app.route("/estado-auth")
def estado_auth():
    if "usuario" not in session:
        return jsonify({"autenticado": False}), 401

    return jsonify({
        "autenticado": True,
        "usuario": session["usuario"]
    })


# Cerrar sesión local
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
