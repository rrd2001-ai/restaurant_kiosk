from app.services import ai_waiter

MENU = [
    {"id": "coke-1", "name": "Coke", "price": 40},
    {"id": "dosa-1", "name": "Masala Dosa", "price": 90},
    {"id": "burger-1", "name": "Chicken Burger", "price": 150},
    {"id": "coffee-1", "name": "Filter Coffee", "price": 30},
]


def mock_rasa(monkeypatch, intent="add_items"):
    monkeypatch.setattr(ai_waiter, "_parse", lambda text: {
        "intent": {"name": intent, "confidence": 0.99}, "entities": []
    })


def test_three_items_with_independent_quantities(monkeypatch):
    mock_rasa(monkeypatch)
    result = ai_waiter.ask_waiter(
        "Three Coke two masala Dosa and four chicken burger", MENU, [], [], False, "Namma Veedu"
    )
    assert result["action"] == "add_items"
    assert result["items_to_add"] == [
        {"id": "coke-1", "quantity": 3},
        {"id": "dosa-1", "quantity": 2},
        {"id": "burger-1", "quantity": 4},
    ]


def test_mixed_digits_and_number_words(monkeypatch):
    mock_rasa(monkeypatch)
    result = ai_waiter.ask_waiter("2 Coke, 3 masala dosa and one filter coffee", MENU, [], [], False, "Namma Veedu")
    assert result["items_to_add"] == [
        {"id": "coke-1", "quantity": 2},
        {"id": "dosa-1", "quantity": 3},
        {"id": "coffee-1", "quantity": 1},
    ]


def test_single_item_defaults_to_one(monkeypatch):
    mock_rasa(monkeypatch)
    result = ai_waiter.ask_waiter("Please add a chicken burger", MENU, [], [], False, "Namma Veedu")
    assert result["items_to_add"] == [{"id": "burger-1", "quantity": 1}]


def test_multi_item_removal(monkeypatch):
    mock_rasa(monkeypatch, intent="remove_items")
    result = ai_waiter.ask_waiter("Remove two Coke and one masala dosa", MENU, [], [], False, "Namma Veedu")
    assert result["action"] == "remove_items"
    assert result["items_to_remove"] == [
        {"id": "coke-1", "quantity": 2},
        {"id": "dosa-1", "quantity": 1},
    ]


def test_repeated_item_mentions_are_combined(monkeypatch):
    mock_rasa(monkeypatch)
    result = ai_waiter.ask_waiter("two Coke and three Coke", MENU, [], [], False, "Namma Veedu")
    assert result["items_to_add"] == [{"id": "coke-1", "quantity": 5}]


def test_availability_question_is_not_automatically_added(monkeypatch):
    mock_rasa(monkeypatch, intent="nlu_fallback")
    result = ai_waiter.ask_waiter("Do you have a Coke?", MENU, [], [], False, "Namma Veedu")
    assert result["action"] == "ask_clarification"
    assert result["items_to_add"] == []
