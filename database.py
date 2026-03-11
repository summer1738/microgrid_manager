"""
SQLite database and SQLAlchemy models for the microgrid manager.
Stores users, appliances, system config, and pending registrations (OTP).
"""
import os
import json
import uuid
from datetime import datetime, timedelta

from flask_sqlalchemy import SQLAlchemy

try:
    from werkzeug.security import check_password_hash
except ImportError:
    def check_password_hash(h, p): return h == p

# Will be set by init_db(app)
db = SQLAlchemy()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "microgrid.db")
USERS_JSON = os.path.join(DATA_DIR, "users.json")
APPLIANCES_JSON = os.path.join(DATA_DIR, "appliances.json")
CONFIG_JSON = os.path.join(DATA_DIR, "system_config.json")


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    system_type = db.Column(db.String(32), nullable=False)
    role = db.Column(db.String(32), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "system_type": self.system_type,
            "role": self.role,
        }


class Appliance(db.Model):
    __tablename__ = "appliances"
    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    power_w = db.Column(db.Float, nullable=False)
    priority = db.Column(db.Integer, nullable=False)
    manually_shed = db.Column(db.Boolean, default=False, nullable=False)
    household = db.Column(db.String(120), nullable=True)  # For community: group appliances by household

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "power_w": self.power_w,
            "priority": self.priority,
            "manually_shed": getattr(self, "manually_shed", False),
            "household": getattr(self, "household", None),
        }


class SystemConfig(db.Model):
    __tablename__ = "system_config"
    id = db.Column(db.Integer, primary_key=True, default=1)
    package = db.Column(db.String(32), nullable=False, default="institutional")


class PendingRegistration(db.Model):
    """Temporary record for email OTP verification before creating the user."""
    __tablename__ = "pending_registrations"
    id = db.Column(db.String(36), primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    system_type = db.Column(db.String(32), nullable=False)
    role = db.Column(db.String(32), nullable=False)
    otp_hash = db.Column(db.String(256), nullable=False)
    otp_expires_at = db.Column(db.DateTime, nullable=False)


OTP_EXPIRY_MINUTES = 10


def init_db(app):
    os.makedirs(DATA_DIR, exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        _add_appliance_household_column_if_missing()
        import_json_if_empty(app)


def _add_appliance_household_column_if_missing():
    """Add household column to appliances if it doesn't exist (SQLite migration)."""
    try:
        with db.engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE appliances ADD COLUMN household TEXT"))
            conn.commit()
    except Exception:
        pass  # Column may already exist


def import_json_if_empty(app):
    """If DB is empty and JSON files exist, import them once."""
    with app.app_context():
        if User.query.first() is not None:
            return
        # Import users
        if os.path.isfile(USERS_JSON):
            try:
                with open(USERS_JSON, "r", encoding="utf-8") as f:
                    for row in json.load(f):
                        u = User(
                            id=row.get("id", str(uuid.uuid4())),
                            name=row["name"],
                            email=row["email"].strip().lower(),
                            password_hash=row["password_hash"],
                            system_type=row["system_type"],
                            role=row["role"],
                        )
                        db.session.add(u)
                db.session.commit()
            except Exception:
                db.session.rollback()
        # Import appliances
        if os.path.isfile(APPLIANCES_JSON):
            try:
                with open(APPLIANCES_JSON, "r", encoding="utf-8") as f:
                    for row in json.load(f):
                        a = Appliance(
                            id=row.get("id", str(uuid.uuid4())),
                            name=row["name"],
                            power_w=float(row["power_w"]),
                            priority=int(row["priority"]),
                            manually_shed=bool(row.get("manually_shed", False)),
                            household=row.get("household") or None,
                        )
                        db.session.add(a)
                db.session.commit()
            except Exception:
                db.session.rollback()
        # Ensure default config
        if SystemConfig.query.get(1) is None:
            package = "institutional"
            if os.path.isfile(CONFIG_JSON):
                try:
                    with open(CONFIG_JSON, "r", encoding="utf-8") as f:
                        package = json.load(f).get("package", package)
                except Exception:
                    pass
            db.session.add(SystemConfig(id=1, package=package))
            db.session.commit()


# ---- User helpers (used by app.py auth) ----

def get_user_by_id(user_id):
    return User.query.get(user_id)


def get_user_by_email(email):
    if not email:
        return None
    return User.query.filter_by(email=email.strip().lower()).first()


def register_user_db(name, email, password_hash, system_type, role):
    if get_user_by_email(email):
        return None
    user_id = str(uuid.uuid4())
    db.session.add(User(
        id=user_id,
        name=name.strip(),
        email=email.strip().lower(),
        password_hash=password_hash,
        system_type=system_type,
        role=role,
    ))
    db.session.commit()
    return user_id


# ---- Pending registration (OTP) helpers ----

def create_pending_registration(email, name, password_hash, system_type, role, otp_hash):
    """Create or replace pending registration for this email. Returns (pending_id, expires_at)."""
    email = email.strip().lower()
    # Remove any existing pending for this email
    PendingRegistration.query.filter_by(email=email).delete()
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    pending_id = str(uuid.uuid4())
    db.session.add(PendingRegistration(
        id=pending_id,
        email=email,
        name=name,
        password_hash=password_hash,
        system_type=system_type,
        role=role,
        otp_hash=otp_hash,
        otp_expires_at=expires_at,
    ))
    db.session.commit()
    return pending_id, expires_at


def get_pending_registration(email):
    if not email:
        return None
    return PendingRegistration.query.filter_by(email=email.strip().lower()).first()


def verify_otp_and_register(email, otp):
    """
    If pending exists, not expired, and OTP matches, create user and delete pending.
    Returns user_id on success, None otherwise.
    """
    pending = get_pending_registration(email)
    if not pending:
        return None
    if datetime.utcnow() > pending.otp_expires_at:
        db.session.delete(pending)
        db.session.commit()
        return None
    if not check_password_hash(pending.otp_hash, str(otp).strip()):
        return None
    user_id = register_user_db(
        name=pending.name,
        email=pending.email,
        password_hash=pending.password_hash,
        system_type=pending.system_type,
        role=pending.role,
    )
    if user_id:
        db.session.delete(pending)
        db.session.commit()
    return user_id


def authenticate(email, password):
    user = get_user_by_email(email)
    if user and check_password_hash(user.password_hash, password):
        return user
    return None


def user_to_dict(user):
    if user is None:
        return None
    return user.to_dict()


# ---- Appliance helpers (used by appliance_routes and ieba_routes) ----

def load_appliances():
    return Appliance.query.all()


def add_appliance_db(name, power_w, priority, household=None):
    a = Appliance(
        id=str(uuid.uuid4()),
        name=name.strip(),
        power_w=float(power_w),
        priority=int(priority),
        manually_shed=False,
        household=(household or "").strip() or None,
    )
    db.session.add(a)
    db.session.commit()
    return a


def get_appliance(appliance_id):
    return Appliance.query.get(appliance_id)


def set_appliance_shed_db(appliance_id, shed):
    a = Appliance.query.get(appliance_id)
    if not a:
        return False
    a.manually_shed = bool(shed)
    db.session.commit()
    return True


def delete_appliance_db(appliance_id):
    a = Appliance.query.get(appliance_id)
    if not a:
        return False
    db.session.delete(a)
    db.session.commit()
    return True


# ---- Config helpers (used by app.py) ----

def get_config():
    row = SystemConfig.query.get(1)
    if row:
        return {"package": row.package}
    return {"package": "institutional"}


def set_config(package):
    row = SystemConfig.query.get(1)
    if row:
        row.package = package
    else:
        db.session.add(SystemConfig(id=1, package=package))
    db.session.commit()
    return get_config()


VALID_SYSTEM_TYPES = ("household", "community", "institutional")
VALID_ROLES = ("operator", "consumer", "maintenance", "utility")
