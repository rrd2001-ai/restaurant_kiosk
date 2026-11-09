from pathlib import Path
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "restaurant_customers.db"))
MENU_PATH = Path(os.getenv("MENU_PATH", BASE_DIR / "menu.json"))
RECEIPTS_DIR = Path(os.getenv("RECEIPTS_DIR", BASE_DIR / "receipts"))
RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
RASA_NLU_URL = os.getenv("RASA_NLU_URL", "http://127.0.0.1:5005/model/parse")
RASA_TIMEOUT = float(os.getenv("RASA_TIMEOUT", "8"))
