import os
import sys
import json
import random
import string

import pandas as pd
from flask import Flask, jsonify, render_template, send_file, request, redirect, url_for, session
from werkzeug.security import generate_password_hash

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database import (
    init_db,
    get_user_by_id,
    get_user_by_email,
    authenticate,
    register_user_db,
    create_pending_registration,
    verify_otp_and_register,
    user_to_dict,
    get_config,
    set_config,
    VALID_SYSTEM_TYPES,
    VALID_ROLES,
)
from email_otp import send_otp_email
from ieba_routes import ieba_bp
from appliance_routes import appliance_bp

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "microgrid-manager-dev-secret-change-in-production")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.register_blueprint(ieba_bp)
app.register_blueprint(appliance_bp)
init_db(app)

# Which routes each role can access (path -> endpoint name for active state)
ROLE_ACCESS = {
    "operator": [
        ("/", "index", "Dashboard"),
        ("/system-status", "system_status", "System status"),
        ("/ieba", "ieba_page", "IEBA performance"),
        ("/appliances", "appliances_page", "Appliances"),
        ("/graphs", "graphs_page", "Graphs"),
        ("/user-types", "user_types_page", "User types"),
        ("/system-design", "system_design_page", "System design"),
        ("/simulator", "simulator_page", "Simulator"),
    ],
    "consumer": [
        ("/", "index", "Dashboard"),
        ("/system-status", "system_status", "System status"),
    ],
    "maintenance": [
        ("/", "index", "Dashboard"),
        ("/system-status", "system_status", "System status"),
        ("/graphs", "graphs_page", "Graphs"),
        ("/appliances", "appliances_page", "Appliances (view)"),
    ],
    "utility": [
        ("/", "index", "Dashboard"),
        ("/system-status", "system_status", "System status"),
    ],
}


def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return wrapped


def role_can_access(role: str, endpoint: str) -> bool:
    for _path, ep, _label in ROLE_ACCESS.get(role, []):
        if ep == endpoint:
            return True
    return False


@app.context_processor
def inject_user_and_nav():
    user = None
    allowed_nav = []
    can_edit_appliances = False
    can_edit_system_design = False
    if "user_id" in session:
        u = get_user_by_id(session["user_id"])
        if u:
            user = user_to_dict(u)
            allowed_nav = ROLE_ACCESS.get(u.role, [])
            can_edit_appliances = u.role == "operator"
            can_edit_system_design = u.role == "operator"
    return {
        "current_user": user,
        "allowed_nav": allowed_nav,
        "can_edit_appliances": can_edit_appliances,
        "can_edit_system_design": can_edit_system_design,
    }


@app.route("/")
@login_required
def index():
    if not role_can_access(session.get("role", ""), "index"):
        return redirect(url_for("index"))
    return render_template("dashboard.html")


@app.route("/system-status")
@login_required
def system_status():
    if not role_can_access(session.get("role", ""), "system_status"):
        return redirect(url_for("index"))
    return render_template("system_status.html")


@app.route("/ieba")
@login_required
def ieba_page():
    if not role_can_access(session.get("role", ""), "ieba_page"):
        return redirect(url_for("index"))
    return render_template("ieba.html")


@app.route("/appliances")
@login_required
def appliances_page():
    if not role_can_access(session.get("role", ""), "appliances_page"):
        return redirect(url_for("index"))
    return render_template("appliances.html")


@app.route("/graphs")
@login_required
def graphs_page():
    if not role_can_access(session.get("role", ""), "graphs_page"):
        return redirect(url_for("index"))
    return render_template("graphs.html")


@app.route("/simulator")
@login_required
def simulator_page():
    if not role_can_access(session.get("role", ""), "simulator_page"):
        return redirect(url_for("index"))
    return render_template("simulator.html")


@app.route("/user-types")
@login_required
def user_types_page():
    if not role_can_access(session.get("role", ""), "user_types_page"):
        return redirect(url_for("index"))
    return render_template("user_types.html")


@app.route("/system-design")
@login_required
def system_design_page():
    if not role_can_access(session.get("role", ""), "system_design_page"):
        return redirect(url_for("index"))
    return render_template("system_design.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        if not email or not password:
            return render_template("login.html", error="Email and password required.")
        user = authenticate(email, password)
        if not user:
            return render_template("login.html", error="Invalid email or password.")
        session["user_id"] = user.id
        session["role"] = user.role
        session["system_type"] = user.system_type
        next_url = request.args.get("next") or url_for("index")
        return redirect(next_url)
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        password2 = request.form.get("password2") or ""
        system_type = (request.form.get("system_type") or "").strip()
        role = (request.form.get("role") or "").strip()
        if not name or not email or not password:
            return render_template("register.html", error="Name, email and password are required.")
        if password != password2:
            return render_template("register.html", error="Passwords do not match.")
        if system_type not in VALID_SYSTEM_TYPES:
            return render_template("register.html", error="Please select a system type.")
        if role not in VALID_ROLES:
            return render_template("register.html", error="Please select a user type.")
        if get_user_by_email(email):
            return render_template("register.html", error="That email is already registered.")
        # Create pending registration and send OTP
        otp = "".join(random.choices(string.digits, k=6))
        otp_hash = generate_password_hash(otp)
        create_pending_registration(
            email=email,
            name=name,
            password_hash=generate_password_hash(password),
            system_type=system_type,
            role=role,
            otp_hash=otp_hash,
        )
        if not send_otp_email(email, otp):
            return render_template("register.html", error="Could not send verification email. Try again later.")
        return redirect(url_for("register_verify", email=email))
    return render_template("register.html", system_types=VALID_SYSTEM_TYPES, roles=VALID_ROLES)


@app.route("/register/verify", methods=["GET", "POST"])
def register_verify():
    if "user_id" in session:
        return redirect(url_for("index"))
    email = (request.args.get("email") or request.form.get("email") or "").strip().lower()
    if request.method == "POST":
        otp = (request.form.get("otp") or "").strip()
        if not email or not otp:
            return render_template("register_verify.html", email=email, error="Email and verification code are required.")
        user_id = verify_otp_and_register(email, otp)
        if not user_id:
            return render_template("register_verify.html", email=email, error="Invalid or expired code. Request a new one from the register page.")
        session["user_id"] = user_id
        u = get_user_by_id(user_id)
        if u:
            session["role"] = u.role
            session["system_type"] = u.system_type
        return redirect(url_for("index"))
    if not email:
        return redirect(url_for("register"))
    return render_template("register_verify.html", email=email)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


def _graph_path(name):
    paths = {
        "pv": os.path.join(PROJECT_ROOT, "forecasting", "pv_forecast_plot.png"),
        "ieba-soc": os.path.join(PROJECT_ROOT, "optimization", "ieba_soc_profile.png"),
        "ieba-loads": os.path.join(PROJECT_ROOT, "optimization", "ieba_load_status.png"),
    }
    return paths.get(name)


@app.route("/graphs/img/<name>")
def graph_image(name):
    if name not in ("pv", "ieba-soc", "ieba-loads"):
        return "", 404
    path = _graph_path(name)
    if not path or not os.path.isfile(path):
        return "", 404
    return send_file(path, mimetype="image/png")


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.route("/api/status")
def get_status():
    # Placeholder static status; later this can be wired to live metrics
    return jsonify(
        {
            "battery_soc": 75.2,
            "critical_load_uptime": "99.8%",
            "forecast_accuracy": "approx 12% MAE on synthetic PV",
        }
    )


@app.route("/api/config", methods=["GET"])
def api_get_config():
    return jsonify(get_config())


@app.route("/api/config", methods=["PATCH"])
def update_config():
    data = request.get_json(silent=True) or {}
    package = data.get("package")
    if package not in ("household", "community", "institutional"):
        return jsonify({"error": "package must be household, community, or institutional"}), 400
    set_config(package)
    return jsonify(get_config())


@app.route("/api/consumption/series")
def consumption_series():
    """Return per-appliance and per-household consumption series for one day (for graphs)."""
    try:
        from optimization.ieba import load_single_day
        from optimization.load_from_appliances import (
            build_appliance_series_from_appliances,
            aggregate_consumption_by_household,
        )
        from database import load_appliances

        day_df = load_single_day()
        timestamps = day_df["timestamp"]
        ts_list = [pd.Timestamp(t).isoformat() for t in timestamps]
    except Exception:
        return jsonify({
            "timestamps": [],
            "appliances": [],
            "households": [],
            "package": get_config().get("package", "institutional"),
        })

    appliances = load_appliances()
    appliance_dicts = [a.to_dict() for a in appliances]
    appliance_series = build_appliance_series_from_appliances(appliance_dicts, timestamps.values)
    # Convert numpy arrays to lists for JSON
    for a in appliance_series:
        a["series"] = [float(x) for x in a["series"]]
    households = aggregate_consumption_by_household(appliance_series, timestamps.values)
    config = get_config()
    return jsonify({
        "timestamps": ts_list,
        "appliances": appliance_series,
        "households": households,
        "package": config.get("package", "institutional"),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
