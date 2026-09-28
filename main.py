import sqlite3
import sys
from datetime import datetime


class SupermarketSystem:
    def __init__(self, db_name="supermarket.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.setup_database()

    def setup_database(self):
        """Creates the necessary tables if they do not exist."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                total_amount REAL NOT NULL
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (sale_id) REFERENCES sales(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)
        self.conn.commit()

    # --- INVENTORY MANAGEMENT ---

    def add_product(self):
        print("\n--- Add New Product ---")
        name = input("Enter product name: ").strip().title()
        try:
            price = float(input("Enter product price ($): "))
            quantity = int(input("Enter product quantity: "))
            if price <= 0 or quantity < 0:
                print("Price must be positive and quantity non-negative.")
                return

            self.cursor.execute(
                "INSERT INTO products (name, price, quantity) VALUES (?, ?, ?)",
                (name, price, quantity)
            )
            self.conn.commit()
            print(f"Product '{name}' added successfully!")
        except sqlite3.IntegrityError:
            print("Error: A product with this name already exists.")
        except ValueError:
            print("Invalid input. Please enter numeric values for price and quantity.")

    def view_inventory(self):
        print("\n--- Current Inventory ---")
        self.cursor.execute("SELECT * FROM products")
        products = self.cursor.fetchall()

        if not products:
            print("Inventory is currently empty.")
            return

        print(f"{'ID':<5} {'Name':<25} {'Price ($)':<12} {'Stock':<10}")
        print("-" * 55)
        for p in products:
            print(f"{p[0]:<5} {p[1]:<25} {p[2]:<12.2f} {p[3]:<10}")

    def update_stock(self):
        print("\n--- Update Stock ---")
        self.view_inventory()
        try:
            prod_id = int(input("\nEnter Product ID to update: "))
            added_qty = int(input("Enter additional quantity to add: "))

            if added_qty <= 0:
                print("Quantity to add must be greater than zero.")
                return

            self.cursor.execute("SELECT quantity FROM products WHERE id = ?", (prod_id,))
            result = self.cursor.fetchone()

            if result:
                new_qty = result[0] + added_qty
                self.cursor.execute("UPDATE products SET quantity = ? WHERE id = ?", (new_qty, prod_id))
                self.conn.commit()
                print("Stock updated successfully!")
            else:
                print("Product ID not found.")
        except ValueError:
            print("Invalid input. Please enter valid integers.")

    def delete_product(self):
        print("\n--- Delete Product ---")
        self.view_inventory()
        try:
            prod_id = int(input("\nEnter Product ID to delete: "))
            self.cursor.execute("DELETE FROM products WHERE id = ?", (prod_id,))
            if self.cursor.rowcount > 0:
                self.conn.commit()
                print("Product deleted successfully!")
            else:
                print("Product ID not found.")
        except ValueError:
            print("Invalid input.")

    # --- BILLING SYSTEM ---

    def create_bill(self):
        print("\n--- Point of Sale / Billing ---")
        self.cursor.execute("SELECT * FROM products WHERE quantity > 0")
        available_products = self.cursor.fetchall()

        if not available_products:
            print("No items available in stock to sell.")
            return

        cart = []  # List of tuples: (product_id, name, unit_price, quantity)

        while True:
            self.view_inventory()
            choice = input("\nEnter Product ID to add to cart (or type 'done' to checkout): ").strip()
            
            if choice.lower() == 'done':
                break

            try:
                prod_id = int(choice)
                self.cursor.execute("SELECT id, name, price, quantity FROM products WHERE id = ?", (prod_id,))
                prod = self.cursor.fetchone()

                if not prod:
                    print("Invalid Product ID.")
                    continue

                p_id, p_name, p_price, p_stock = prod
                
                # Check quantity already in cart
                already_in_cart = sum(item[3] for item in cart if item[0] == p_id)
                available_stock = p_stock - already_in_cart

                if available_stock <= 0:
                    print("No more stock available for this item.")
                    continue

                qty = int(input(f"Enter quantity for '{p_name}' (Available: {available_stock}): "))
                
                if qty <= 0:
                    print("Quantity must be greater than zero.")
                    continue
                elif qty > available_stock:
                    print("Cannot add more than available stock.")
                    continue

                cart.append((p_id, p_name, p_price, qty))
                print(f"Added {qty} x '{p_name}' to cart.")

            except ValueError:
                print("Invalid input. Please enter a valid Product ID or 'done'.")

        if not cart:
            print("Cart is empty. Transaction cancelled.")
            return

        # Process Checkout
        self.process_checkout(cart)

    def process_checkout(self, cart):
        subtotal = sum(item[2] * item[3] for item in cart)
        discount_percent = 0.0

        try:
            disc_input = input("Enter discount percentage (0-100, press Enter for 0): ").strip()
            if disc_input:
                discount_percent = float(disc_input)
                if not (0 <= discount_percent <= 100):
                    print("Invalid discount range. Applying 0%.")
                    discount_percent = 0.0
        except ValueError:
            print("Invalid input. Applying 0% discount.")

        discount_amount = (subtotal * discount_percent) / 100
        tax = (subtotal - discount_amount) * 0.05  # 5% Tax
        grand_total = (subtotal - discount_amount) + tax

        # Save Sale to DB
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute("INSERT INTO sales (timestamp, total_amount) VALUES (?, ?)", (timestamp, grand_total))
        sale_id = self.cursor.lastrowid

        # Update Stock and Save Sale Items
        for p_id, p_name, p_price, qty in cart:
            self.cursor.execute(
                "INSERT INTO sale_items (sale_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                (sale_id, p_id, qty, p_price)
            )
            self.cursor.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?", (qty, p_id))

        self.conn.commit()

        # Print Invoice
        print("\n" + "=" * 45)
        print("          SUPERMARKET RECEIPT          ")
        print("=" * 45)
        print(f"Invoice ID: #{sale_id:<10} Date: {timestamp}")
        print("-" * 45)
        print(f"{'Item':<20} {'Qty':<5} {'Price':<8} {'Total':<8}")
        print("-" * 45)
        
        for p_id, p_name, p_price, qty in cart:
            line_total = p_price * qty
            print(f"{p_name:<20} {qty:<5} ${p_price:<7.2f} ${line_total:<7.2f}")

        print("-" * 45)
        print(f"{'Subtotal:':<34} ${subtotal:.2f}")
        print(f"{'Discount (' + str(discount_percent) + '%):':<34} -${discount_amount:.2f}")
        print(f"{'Tax (5%):':<34} +${tax:.2f}")
        print(f"{'Grand Total:':<34} ${grand_total:.2f}")
        print("=" * 45)
        print("       Thank you for shopping with us!       \n")

    # --- REPORTS ---

    def view_sales_report(self):
        print("\n--- Sales History ---")
        self.cursor.execute("SELECT * FROM sales ORDER BY id DESC")
        sales = self.cursor.fetchall()

        if not sales:
            print("No sales history recorded yet.")
            return

        print(f"{'Sale ID':<10} {'Timestamp':<22} {'Total ($)':<12}")
        print("-" * 46)
        total_revenue = 0
        for s in sales:
            print(f"#{s[0]:<9} {s[1]:<22} ${s[2]:<11.2f}")
            total_revenue += s[2]
        
        print("-" * 46)
        print(f"Total Cumulative Revenue: ${total_revenue:.2f}\n")

    def close(self):
        self.conn.close()


def main():
    system = SupermarketSystem()

    while True:
        print("\n==========================================")
        print("   SUPERMARKET MANAGEMENT & BILLING SYSTEM")
        print("==========================================")
        print("1. Create Bill / Point of Sale (POS)")
        print("2. View Inventory")
        print("3. Add New Product")
        print("4. Restock Existing Product")
        print("5. Delete Product")
        print("6. View Sales Report")
        print("7. Exit")
        
        choice = input("\nSelect an option (1-7): ").strip()

        if choice == '1':
            system.create_bill()
        elif choice == '2':
            system.view_inventory()
        elif choice == '3':
            system.add_product()
        elif choice == '4':
            system.update_stock()
        elif choice == '5':
            system.delete_product()
        elif choice == '6':
            system.view_sales_report()
        elif choice == '7':
            system.close()
            print("\nExiting system. Goodbye!")
            sys.exit()
        else:
            print("Invalid selection! Please enter a number between 1 and 7.")


if __name__ == "__main__":
    main()
