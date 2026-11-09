# Namma Veedu — AI Restaurant Kiosk

A browser-based restaurant kiosk with English text and voice ordering, FastAPI, SQLite, Rasa NLU, server-controlled cart/checkout, and PDF receipts.

## Architecture

- **FastAPI** serves the kiosk, menu, sessions, cart, checkout, and receipt endpoints.
- **Rasa NLU** classifies customer intent. It runs in a separate Python 3.10 environment because Rasa Open Source 3.6.21 does not support the FastAPI app's Python 3.12 environment.
- **Python services** resolve menu items against the live menu and own all cart mutations, prices, session state, checkout confirmation, and receipt generation. Rasa never supplies trusted item IDs or prices.
- **SQLite** stores sessions, customers, and orders.
- **Browser UI** supports typed orders and speech recognition / spoken replies where the browser supports them.

## 1. Install the FastAPI application

Use Python 3.12 for the web application:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

## 2. Install Rasa in its own environment (macOS)

Rasa Open Source 3.6.21 requires Python 3.10. Do not install it in `.venv`.

```bash
brew install python@3.10
"$(brew --prefix python@3.10)/bin/python3.10" -m venv .rasa-venv
source .rasa-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "rasa==3.6.21"
```

## 3. Train the NLU model

From the project root, with `.rasa-venv` active:

```bash
chmod +x scripts/train_rasa.sh scripts/start_rasa.sh
./scripts/train_rasa.sh
```

## 4. Start both services

Terminal 1 — Rasa NLU:

```bash
source .rasa-venv/bin/activate
./scripts/start_rasa.sh
```

Terminal 2 — FastAPI:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. Keep Rasa bound to localhost; do not expose port 5005 publicly.

## Multi-item ordering

The waiter scans the entire message against the live menu and associates each quantity with the next mentioned item. It supports digits and number words, repeated mentions (combined by item ID), and multi-item removals.

Example: `Three Coke, two Masala Dosa and four Chicken Burger` creates three distinct cart changes with quantities 3, 2, and 4. IDs and prices always come from the server's menu.

## Tests

Run from the project root with the FastAPI environment active:

```bash
python -m pytest -q
```

The multi-item tests mock the Rasa response, so they do not require a running Rasa server.

## Configuration

See `.env.example`. The default database is `restaurant_customers.db` in the project root to preserve the existing customer database. Override `DB_PATH` only when you intentionally use another database file. Do not delete an existing database when upgrading.

## Notes

- The NLU examples are a starter dataset. Add varied real customer phrasing to `rasa_nlu/data/nlu.yml`, then retrain.
- Keep menu item IDs stable when updating `menu.json`.
- `ask_price` and `ask_ingredients` intents are recognized, but detailed answers require the relevant fields in the menu data and route/service support.
- Voice recognition depends on browser support and microphone permission; text ordering remains available.
