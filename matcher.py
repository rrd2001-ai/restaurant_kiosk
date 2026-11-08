import json
from rapidfuzz import process, fuzz

with open("menu.json", "r") as f:
    menu_data = json.load(f)

menu_items = {item["name"]: item for item in menu_data["items"]}
menu_names = list(menu_items.keys())
STOP_WORDS = {"i", "want", "give", "me", "please", "would", "like", "a", "an", "the", "can", "you", "get"}

def clean_spoken_text(text):
    words = text.lower().split()
    return " ".join([w for w in words if w not in STOP_WORDS])

def match_item(spoken_text):
    cleaned = clean_spoken_text(spoken_text)
    query = cleaned if cleaned else spoken_text
    
    best_match, score, _ = process.extractOne(query, menu_names, scorer=fuzz.WRatio)
    if score >= 65:
        return menu_items[best_match], score
    return None, score