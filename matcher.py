import json
from rapidfuzz import process, fuzz

with open("menu.json", "r") as f:
    menu_data = json.load(f)

menu_items = {item["name"]: item for item in menu_data["items"]}
menu_names = list(menu_items.keys())
STOP_WORDS = {"i", "want", "give", "me", "please", "would", "like", "a", "an", "the", "can", "you", "get", "and"}

def match_multiple_items(spoken_text):
    # Split text into chunks by 'and' or commas
    phrases = spoken_text.lower().replace(" and ", ",").split(",")
    matched_results = []
    
    for phrase in phrases:
        cleaned_words = [w for w in phrase.strip().split() if w not in STOP_WORDS]
        if not cleaned_words:
            continue
        query = " ".join(cleaned_words)
        
        best_match, score, _ = process.extractOne(query, menu_names, scorer=fuzz.WRatio)
        if score >= 60:
            item = menu_items[best_match]
            existing = next((i for i in matched_results if i["id"] == item["id"]), None)
            if existing:
                existing["quantity"] += 1
            else:
                matched_results.append({
                    "id": item["id"],
                    "name": item["name"],
                    "price": item["price"],
                    "quantity": 1
                })
                
    return matched_results