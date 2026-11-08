import sqlite3

DB_FILE = "restaurant_customers.db"

def init_customer_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            phone TEXT PRIMARY KEY,
            name TEXT,
            last_order TEXT,
            visit_count INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def get_customer(phone):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name, last_order, visit_count FROM customers WHERE phone = ?", (phone,))
    row = cursor.fetchone()
    conn.close()
    return row

def save_customer(phone, name, order_summary):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT visit_count FROM customers WHERE phone = ?", (phone,))
    row = cursor.fetchone()
    
    if row:
        new_count = row[0] + 1
        cursor.execute("UPDATE customers SET last_order = ?, visit_count = ? WHERE phone = ?", (order_summary, new_count, phone))
    else:
        cursor.execute("INSERT INTO customers (phone, name, last_order, visit_count) VALUES (?, ?, ?, 1)", (phone, name, order_summary))
        
    conn.commit()
    conn.close()