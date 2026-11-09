from app.api.routes import is_done, checkout_decision

def test_done_starts_checkout_but_is_not_approval():
    assert is_done("That's all")
    assert checkout_decision("that's all") is None

def test_explicit_confirmation():
    assert checkout_decision("Yes") == "yes"
    assert checkout_decision("No") == "no"
