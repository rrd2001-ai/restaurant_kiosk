from app.services.cart_service import cart_details, add_items, remove_items

MENU=[{"id":"A","name":"Tea","price":20},{"id":"B","name":"Coffee","price":30}]
BY_ID={x['id']:x for x in MENU}

def test_add_and_total():
    cart={}; add_items(cart,[{"id":"A","quantity":2},{"id":"B","quantity":1}],BY_ID)
    assert cart_details(cart,BY_ID)['total']==70
    assert cart_details(cart,BY_ID)['count']==3

def test_remove_caps_at_zero():
    cart={'A':1}; remove_items(cart,[{"id":"A","quantity":2}])
    assert cart=={}
