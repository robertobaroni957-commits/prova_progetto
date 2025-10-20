# utils/auth_decorators.py

from functools import wraps
from flask import session, redirect, url_for, flash

# 🔐 Accesso riservato agli admin
def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_role') != 'admin':
            flash("⛔ Accesso riservato agli admin", "danger")
            return redirect(url_for('auth.login_admin'))
        return f(*args, **kwargs)
    return decorated_function

# 🔐 Accesso riservato ai capitani
def require_captain(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_role') != 'captain':
            flash("⛔ Accesso riservato ai capitani", "danger")
            return redirect(url_for('auth.login_captain'))
        return f(*args, **kwargs)
    return decorated_function

# 🔐 Accesso riservato a ruoli multipli
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