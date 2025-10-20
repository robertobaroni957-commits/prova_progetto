from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from functools import wraps
import sqlite3

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

DB_PATH = "zrl.db"

# 🔌 Connessione al database
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# 🔐 Decoratori di accesso
def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_role') != 'admin':
            flash("⛔ Accesso riservato agli admin", "danger")
            return redirect(url_for('auth.login_admin'))
        return f(*args, **kwargs)
    return decorated_function

def require_captain(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_role') != 'captain':
            flash("⛔ Accesso riservato ai capitani", "danger")
            return redirect(url_for('auth.login_captain'))
        return f(*args, **kwargs)
    return decorated_function

def require_roles(allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            role = session.get("user_role")
            if role not in allowed_roles:
                flash("⛔ Accesso non autorizzato", "danger")
                return redirect(url_for("auth.login_admin"))
            return f(*args, **kwargs)
        return wrapped
    return decorator

# 🔐 Login generico
def login_user(email, password, role):
    conn = get_db()
    cur = conn.cursor()
    user = cur.execute("""
        SELECT * FROM users WHERE email = ? AND role = ? AND active = 1
    """, (email, role)).fetchone()

    if user and check_password_hash(user["password"], password):
        session["user_id"] = user["id"]
        session["user_email"] = user["email"]
        session["user_role"] = user["role"]
        if role == "captain":
            session["team_id"] = user["team_id"]
        return user
    return None

# 🧑‍💼 Login Admin
@auth_bp.route('/login_admin', methods=['GET', 'POST'])
def login_admin():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            flash("Compila tutti i campi", "danger")
            return redirect(url_for("auth.login_admin"))

        user = login_user(email, password, role="admin")
        if user:
            flash("✅ Accesso admin effettuato", "success")
            return redirect(url_for("admin_panel.admin_dashboard"))
        else:
            flash("❌ Credenziali non valide", "danger")
            return redirect(url_for("auth.login_admin"))

    return render_template("auth/login_admin.html")

# 🚴‍♂️ Login Capitano
@auth_bp.route('/login_captain', methods=['GET', 'POST'])
def login_captain():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            flash("Compila tutti i campi", "danger")
            return redirect(url_for("auth.login_captain"))

        user = login_user(email, password, role="captain")
        if user:
            flash("✅ Accesso capitano effettuato", "success")
            return redirect(url_for("captain.captain_dashboard"))
        else:
            flash("❌ Credenziali non valide", "danger")
            return redirect(url_for("auth.login_captain"))

    return render_template("auth/login_captain.html")

# 🔓 Logout
@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("👋 Logout effettuato", "info")
    return redirect(url_for("main.home"))

# 🔁 Recupero password (placeholder)
@auth_bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    # Da implementare
    return render_template("auth/forgot_password.html")