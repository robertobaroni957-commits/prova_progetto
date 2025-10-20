from flask import Blueprint, render_template, current_app

debug_bp = Blueprint("debug", __name__, url_prefix="/debug")

@debug_bp.route("/routes")
def list_routes():
    routes = []
    for rule in current_app.url_map.iter_rules():
        routes.append({
            "endpoint": rule.endpoint,
            "rule": rule.rule,
            "methods": ", ".join(rule.methods - {"HEAD", "OPTIONS"})
        })
    return render_template("debug/routes.html", routes=routes)