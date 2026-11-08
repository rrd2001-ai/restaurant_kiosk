import json
from llama_cpp import Llama

# Load quantized local 0.5B model
llm = Llama.from_pretrained(
    repo_id="Qwen/Qwen2.5-0.5B-Instruct-GGUF",
    filename="*q4_k_m.gguf",
    verbose=False
)

ORDER_SYSTEM_PROMPT = """You are a polite AI waiter for Namma Veedu Restaurant.
Classify the user's speech into an intent: either "order" (if they are adding food/drinks) or "checkout" (if they are finishing, confirming, saying "that is all", or asking for the bill/receipt).

Available Menu Items:
- Paneer Burger
- Chicken Burger
- Masala Dosa
- Filter Coffee
- Pepperoni Pizza
- Coke

Return ONLY a raw JSON object (no markdown formatting, no backticks) matching this exact structure:
{
  "intent": "order",
  "items": [{"name": "Exact Menu Item Name", "quantity": 1}],
  "waiter_reply": "Got it! I have added 1 Chicken Burger to your order. Anything else?"
}"""

NAME_SYSTEM_PROMPT = """You are an AI assistant for Namma Veedu Restaurant.
Extract ONLY the customer's real name from their spoken sentence (e.g., "Hi I am Ravi" -> "Ravi", "My name is Priya" -> "Priya").

Return ONLY a raw JSON object (no markdown formatting, no backticks) matching this structure:
{
  "name": "Extracted Name Only"
}"""

def process_name_command(user_speech: str):
    prompt = f"<|im_start|>system\n{NAME_SYSTEM_PROMPT}<|im_end|>\n<|im_start|>user\n{user_speech}<|im_end|>\n<|im_start|>assistant\n"
    
    output = llm(
        prompt,
        max_tokens=40,
        temperature=0.1,
        stop=["<|im_end|>"]
    )
    
    raw_text = output["choices"][0]["text"].strip()
    try:
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        return json.loads(raw_text.strip())
    except Exception:
        return {"name": user_speech.strip()}

def process_voice_command(user_speech: str):
    prompt = f"<|im_start|>system\n{ORDER_SYSTEM_PROMPT}<|im_end|>\n<|im_start|>user\n{user_speech}<|im_end|>\n<|im_start|>assistant\n"
    
    output = llm(
        prompt,
        max_tokens=150,
        temperature=0.1,
        stop=["<|im_end|>"]
    )
    
    raw_text = output["choices"][0]["text"].strip()
    
    try:
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
            
        response_data = json.loads(raw_text.strip())
        
        # Handle checkout intent cleanly
        if response_data.get("intent") == "checkout":
            return {
                "intent": "checkout",
                "items": [],
                "waiter_reply": "Certainly! Proceeding to your final bill and receipt."
            }
            
        # Format item confirmation reply
        items = response_data.get("items", [])
        if items:
            parts = [f"{i.get('quantity', 1)} {i.get('name')}" for i in items]
            if len(parts) > 1:
                item_desc = ", ".join(parts[:-1]) + " and " + parts[-1]
            else:
                item_desc = parts[0]
            response_data["waiter_reply"] = f"Got it! I have added {item_desc} to your order. Anything else?"
            response_data["intent"] = "order"
        else:
            response_data["intent"] = "order"
            response_data["waiter_reply"] = "I didn't quite catch those items. Could you repeat them?"
                
        return response_data
    except Exception:
        return {
            "intent": "order",
            "items": [],
            "waiter_reply": "I couldn't quite catch that. Could you repeat your order?"
        }