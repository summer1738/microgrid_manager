# Adaptive AI-Driven Microgrid Manager for Off-Grid Solar Systems

A simulation-based microgrid management system with PV forecasting, intelligent energy budgeting (IEBA), and a user control & load prioritization interface (UCLPI). Built for final-year project use and scalable to household, community, and institutional deployments.

## Features

- **PV forecasting** — LSTM-based next-hour PV generation forecast
- **IEBA** — Intelligent Energy Budgeting Algorithm for load prioritization and battery SOC management
- **UCLPI** — Web dashboard to register appliances, set priorities (critical / essential / non-essential), and manually shed loads
- **System design** — User types, registration flow, and three system packages (Household, Community, Institutional)
- **Graphs** — Pre-generated IEBA and PV forecast plots
- **Auth & roles** — Login/register; roles (operator, consumer, maintenance, utility) control sidebar and edit access
- **SQLite** — Users, appliances, and system config stored in `data/microgrid.db`; existing JSON files are imported once when the DB is empty

## Requirements

- Python 3.10+
- See `api/` and project root for running the app; forecasting uses TensorFlow/Keras, scikit-learn, pandas, matplotlib

## Quick start

### 1. Create and activate a virtual environment

```bash
cd microgrid_manager
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate   # Linux/macOS
```

### 2. Install dependencies

```bash
pip install flask flask-sqlalchemy werkzeug pandas numpy scikit-learn tensorflow matplotlib joblib
```

### 3. Generate training data (if not already present)

From project root:

```bash
python generate_training_data.py
```

### 4. Train the PV model (optional, for forecasting)

```bash
cd forecasting
python train_lstm_pv.py
cd ..
```

### 5. Generate IEBA plots (optional)

```bash
cd optimization
python plot_ieba_day.py
cd ..
```

### 6. Run the web application

```bash
cd api
python app.py
```

Open **http://localhost:5000** in a browser. You will be redirected to **Log in**. If you have no account, use **Register** to create one; you will receive a **6-digit OTP by email** to verify your address (see [Email / OTP](#email--otp) below). Choose **System type** and **User type**; your role determines which pages you can access. After logging in, use the sidebar to navigate.

### Email / OTP

Registration requires email verification. A one-time code is sent to the address you provide. If SMTP is not configured, the app logs the OTP to the server console (and in logs) so you can copy it in development. To send real email, set:

- `SMTP_HOST` — e.g. `smtp.gmail.com`
- `SMTP_PORT` — default `587`
- `SMTP_USER` — your account
- `SMTP_PASSWORD` — app password or account password
- `MAIL_FROM` — optional; defaults to `SMTP_USER`

Codes expire after 10 minutes.

### Verifying the model (virtual hardware → system)

The virtual hardware simulator sends sensor data the same way real hardware would. To confirm the full flow:

1. **Simulator feeds the system** — Log in as an operator, open **Simulator**, leave **Feed data to system** on. The page POSTs sensor data to `POST /api/hardware/ingest` every tick.
2. **Dashboard shows live data** — Open **Dashboard**. Within a few seconds the status badge should show **Live: simulator**, and Battery SOC, **PV power (live)**, and **Load (live)** should update every 5 seconds.
3. **Circuit reflects sensors** — Open **Circuit**. The diagram should show the same PV, battery, and load values, and the badge **Live from simulator**.
4. **Same API as real hardware** — Real devices would POST the same JSON to `/api/hardware/ingest`; the rest of the system (status, circuit, dashboard) would behave identically.

## Project structure

```
microgrid_manager/
├── api/                 # Flask app and dashboard
│   ├── app.py           # Main app, routes, auth, graph image serving
│   ├── email_otp.py     # Send OTP by email (SMTP or console in dev)
│   ├── ieba_routes.py   # IEBA perfect / forecast / custom
│   ├── appliance_routes.py
│   └── templates/       # HTML (base, dashboard, ieba, appliances, graphs, user_types, system_design)
├── data/
│   ├── microgrid.db     # SQLite DB (users, appliances, system_config)
│   ├── appliances.json # Optional: imported into DB when empty
│   ├── users.json       # Optional: imported into DB when empty
│   ├── system_config.json
│   ├── processed/       # training_data_30_days.csv
│   └── raw/
├── database.py          # SQLAlchemy models and DB helpers (init_db, import from JSON)
├── domain/
│   ├── appliances.py    # Legacy / used by optimization load builder
│   └── users.py        # Legacy; auth uses database.py
├── docs/
│   ├── USER_TYPES.md
│   └── REGISTRATION_AND_PACKAGES.md
├── forecasting/
│   ├── train_lstm_pv.py
│   ├── predict_pv.py
│   ├── pv_lstm_model.keras
│   └── pv_scaler.joblib
├── optimization/
│   ├── ieba.py
│   ├── ieba_with_pv_forecast.py
│   ├── load_from_appliances.py
│   └── plot_ieba_day.py
├── generate_training_data.py
├── requirements.txt
└── README.md
```

## Documentation

- **User types** — `docs/USER_TYPES.md` (Operator, Energy consumers, Maintenance, Utility)
- **Registration & packages** — `docs/REGISTRATION_AND_PACKAGES.md` (Household, Community, Institutional)

## API overview

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard (login required) |
| `GET /login` | Log in page |
| `GET /register` | Registration page |
| `POST /logout` | Log out |
| `GET /system-status` | System status page |
| `GET /ieba` | IEBA performance page |
| `GET /appliances` | Appliances (UCLPI) page |
| `GET /graphs` | Graphs page |
| `GET /user-types` | User types page |
| `GET /system-design` | System design (registration & packages) |
| `GET /api/status` | JSON status snapshot |
| `GET /api/config` | Current system config (e.g. package) |
| `PATCH /api/config` | Update config (body: `{"package": "household"\|"community"\|"institutional"}`) |
| `GET /ieba/custom` | IEBA run with registered appliances |
| `GET /ieba/forecast` | IEBA Perfect vs Forecast comparison |
| `GET /appliances/` | List appliances |
| `POST /appliances/` | Add appliance |
| `PATCH /appliances/<id>/shed` | Set manual shed on/off |
| `DELETE /appliances/<id>` | Remove appliance |

## License

Project use as required by your institution.
