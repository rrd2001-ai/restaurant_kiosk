import json
from rapidfuzz import process, fuzz

with open("menu.json", "r") as f:
    menu_data = json.load(f)

menu_items = {item["name"]: item for item in menu_data["items"]}
menu_names = list(menu_items.keys())

# Common conversational filler words to strip out of spoken text
STOP_WORDS = {"i", "want", "give", "me", "please", "would", "like", "a", "an", "the", "can", "you", "get"}

def clean_spoken_text(text):
    words = text.lower().split()
    filtered_words = [w for w in words if w not in STOP_WORDS]
    return " ".join(filtered_words)

def match_spoken_item(spoken_text):
    cleaned_text = clean_spoken_text(spoken_text)
    
    # Fallback if cleaning removed everything
    query = cleaned_text if cleaned_text else spoken_text
    
    best_match, score, _ = process.extractOne(query, menu_names, scorer=fuzz.WRatio)
    
    if score >= 65:  # Reliable threshold after cleaning
        matched_item = menu_items[best_match]
        return matched_item, score, query
    return None, score, query

test_phrases = [
    "paneer burgre",
    "give me masala dosha",
    "coke please",
    "i would like a chicken burger"
]

print("--- Testing Preprocessed RapidFuzz Matching ---")
for phrase in test_phrases:
    item, conf, cleaned = match_spoken_item(phrase)
    if item:
        print(f"Spoken: '{phrase}' ➔ Cleaned: '{cleaned}' ➔ Matched: {item['name']} (₹{item['price']}) [Conf: {conf:.1f}]")
    else:
        print(f"Spoken: '{phrase}' ➔ Cleaned: '{cleaned}' ➔ No match found (Score: {conf:.1f})")