# README.md

# PayShield AI

An end‑to‑end **AI‑powered real‑time financial fraud detection** system built as a single Streamlit application.

## Features
- Secure email/password authentication (bcrypt, PostgreSQL).
- Trainable fraud detection model (RandomForest, XGBoost, etc.) with automatic preprocessing.
- Real‑time transaction simulation that updates a live dashboard.
- PostgreSQL storage for users, transactions, predictions, alerts, reports and chat history.
- AI‑generated explanations for each prediction using OpenRouter.
- Interactive Plotly visualisations, downloadable CSV reports, and an AI chatbot.
- Comprehensive logging and automated pytest suite.

## Project Structure
```
PayShieldAI/
│   .gitignore
│   README.md
│   requirements.txt
│   .env.example
│   main.py
│
├─ src/
│   ├─ __init__.py
│   ├─ config.py
│   ├─ db/
│   │   ├─ __init__.py
│   │   ├─ base.py
│   │   ├─ models.py
│   │   └─ session.py
│   ├─ security/
│   │   ├─ __init__.py
│   │   ├─ password.py
│   │   └─ auth.py
│   ├─ ml/
│   │   ├─ __init__.py
│   │   ├─ data_loader.py
│   │   ├─ preprocessing.py
│   │   ├─ train.py
│   │   ├─ inference.py
│   │   └─ explain.py
│   ├─ simulation/
│   │   ├─ __init__.py
│   │   └─ runner.py
│   ├─ ui/
│   │   ├─ __init__.py
│   │   ├─ components/
│   │   │   ├─ navigation.py
│   │   │   ├─ metrics_card.py
│   │   │   └─ alert_banner.py
│   │   └─ pages/
│   │       ├─ 1_Login.py
│   │       ├─ 2_Dashboard.py
│   │       ├─ 3_RealTimeMonitoring.py
│   │       ├─ 4_TransactionSimulation.py
│   │       ├─ 5_PredictionHistory.py
│   │       ├─ 6_Analytics.py
│   │       ├─ 7_Reports.py
│   │       ├─ 8_Alerts.py
│   │       ├─ 9_Chatbot.py
│   │       ├─ 10_Settings.py
│   │       └─ 11_About.py
│   └─ logging/
│       └─ logger.py
│
└─ tests/
    ├─ __init__.py
    ├─ test_auth.py
    ├─ test_data_loader.py
    ├─ test_preprocessing.py
    ├─ test_train.py
    ├─ test_simulation.py
    └─ test_chatbot.py
```

## Setup
```bash
# Clone the repo (once we push it)
git clone <repo-url>
cd PayShieldAI

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create a .env file from the example and fill in your credentials
cp .env.example .env
# Edit .env with your DATABASE_URL and OPENROUTER_API_KEY

# Initialise the database (tables are auto‑created on first run)
python -c "import src.db.session; from src.db.base import Base; from src.config import settings; Base.metadata.create_all(src.db.session.engine)"

# Train the fraud model (runs once, creates models/ folder)
python -m src.ml.train

# Run the Streamlit app
streamlit run main.py
```

## Testing
```bash
pytest -q
```

---
*This project is for educational purposes only and **must not** be used in production banking environments.*
