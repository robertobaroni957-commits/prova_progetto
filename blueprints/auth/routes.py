from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from functools import wraps
import sqlite3

# Blueprint di autenticazione
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

DB_PATH = "zrl.db"

# ============================================================
# 🗄️ Connessione al database
# ============================================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# 🔐 Decoratori di protezione
# ============================================================
def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_role") != "admin":
            flash("⛔ Accesso riservato agli amministratori", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


def require_captain(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_role") != "captain":
            flash("⛔ Accesso riservato ai capitani", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


def require_roles(allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            role = session.get("user_role")
            if role not in allowed_roles:
                flash("⛔ Accesso non autorizzato", "danger")
                return redirect(url_for("auth.login"))
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ============================================================
# 🧠 Login utente generico
# ============================================================
def login_user(email, password, role):
    conn = get_db()
    cur = conn.cursor()
    user = cur.execute("""
        SELECT * FROM users
        WHERE email = ? AND role = ? AND active = 1
    """, (email, role)).fetchone()

    if user and check_password_hash(user["password"], password):
        session["user_id"] = user["id"]
        session["user_email"] = user["email"]
        session["user_role"] = user["role"]
        if role == "captain":
            session["team_id"] = user["team_id"]
        return user
    return None


# ============================================================
# 🔑 LOGIN UNIFICATO (Admin + Captain)
# ============================================================
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")

        if not email or not password or not role:
            flash("⚠️ Compila tutti i campi", "warning")
            return redirect(url_for("auth.login"))

        user = login_user(email, password, role=role)
        if user:
            flash(f"✅ Accesso come {role} effettuato", "success")
            if role == "admin":
                return redirect(url_for("admin_panel.admin_dashboard"))
            elif role == "captain":
                return redirect(url_for("captain.captain_dashboard"))
        else:
            flash("❌ Credenziali non valide o utente inattivo", "danger")
            return redirect(url_for("auth.login"))

    return render_template("auth/login.html")


# ============================================================
# 🔓 Logout
# ============================================================
@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("👋 Logout effettuato con successo", "info")
    return redirect(url_for("auth.login"))


# ============================================================
# 🔁 Recupero password (Placeholder)
# ============================================================
@auth_bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    return render_template("auth/forgot_password.html")
