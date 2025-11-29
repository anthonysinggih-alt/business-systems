from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from databases import Product, ProductSession, CartItem, CartSession, Transaction, TransactionSession
import json
import csv
import io
from datetime import datetime

app = Flask(__name__)

# Payment types available
PAYMENT_TYPES = ["Cash", "Credit Card", "Debit Card", "E-Wallet"]


# ---------------- HOME ROUTE ----------------
@app.route('/')
def index():
    return render_template('index.html')


# ---------------- ADMIN ROUTES ----------------
@app.route('/admin')
def admin():
    session = ProductSession()
    products = session.query(Product).all()
    session.close()
    return render_template('admin.html', products=products)


@app.route('/admin/add_product', methods=['POST'])
def add_product():
    session = ProductSession()

    new_product = Product(
        product_id=request.form['product_id'],
        product_name=request.form['product_name'],
        unit_price=float(request.form['unit_price'])
    )

    session.add(new_product)
    session.commit()
    session.close()

    return redirect(url_for('admin'))


@app.route('/admin/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    session = ProductSession()
    product = session.query(Product).filter_by(id=product_id).first()
    if product:
        session.delete(product)
        session.commit()
    session.close()
    return redirect(url_for('admin'))


# ---------------- CUSTOMER ROUTES ----------------
@app.route('/customer')
def customer():
    session = ProductSession()
    products = session.query(Product).all()
    session.close()

    cart_session = CartSession()
    cart_items = cart_session.query(CartItem).filter_by(session_id="current").all()
    cart_session.close()

    subtotal = sum(item.unit_price * item.quantity for item in cart_items)

    return render_template('customer.html', products=products, cart_items=cart_items, subtotal=subtotal,
                           payment_types=PAYMENT_TYPES)


@app.route('/customer/add_to_cart', methods=['POST'])
def add_to_cart():
    session = CartSession()

    product_id = request.form['product_id']
    product_name = request.form['product_name']
    unit_price = float(request.form['unit_price'])

    # Check if item already in cart
    existing_item = session.query(CartItem).filter_by(
        product_id=product_id,
        session_id="current"
    ).first()

    if existing_item:
        existing_item.quantity += 1
    else:
        new_cart_item = CartItem(
            product_id=product_id,
            product_name=product_name,
            unit_price=unit_price,
            quantity=1,
            session_id="current"
        )
        session.add(new_cart_item)

    session.commit()
    session.close()

    return redirect(url_for('customer'))


@app.route('/customer/remove_from_cart/<int:cart_id>', methods=['POST'])
def remove_from_cart(cart_id):
    session = CartSession()
    cart_item = session.query(CartItem).filter_by(id=cart_id).first()
    if cart_item:
        session.delete(cart_item)
        session.commit()
    session.close()
    return redirect(url_for('customer'))


@app.route('/customer/checkout', methods=['POST'])
def checkout():
    cart_session = CartSession()
    cart_items = cart_session.query(CartItem).filter_by(session_id="current").all()

    if not cart_items:
        cart_session.close()
        return redirect(url_for('customer'))

    # Get payment type from form
    payment_type = request.form.get('payment_type', 'Cash')

    # Calculate totals
    subtotal = sum(item.unit_price * item.quantity for item in cart_items)
    tax = subtotal * 0.1  # 10% tax
    total = subtotal + tax

    # Prepare items for storage
    items_data = [
        {
            "product_name": item.product_name,
            "quantity": item.quantity,
            "unit_price": item.unit_price
        }
        for item in cart_items
    ]

    # Save transaction with payment type
    trans_session = TransactionSession()
    new_transaction = Transaction(
        items=json.dumps(items_data),
        subtotal=subtotal,
        tax=tax,
        total=total,
        payment_amount=total,
        change_amount=0.0,
        payment_type=payment_type
    )
    trans_session.add(new_transaction)
    trans_session.commit()
    trans_session.close()

    # Clear cart
    for item in cart_items:
        cart_session.delete(item)
    cart_session.commit()
    cart_session.close()

    # Redirect back to customer page (blank slate)
    return redirect(url_for('customer'))


# ---------------- TRANSACTIONS ROUTE ----------------
@app.route('/transactions')
def transactions():
    session = TransactionSession()
    all_transactions = session.query(Transaction).order_by(Transaction.transaction_date.desc()).all()

    # Parse JSON items for each transaction
    transactions_data = []
    for trans in all_transactions:
        transactions_data.append({
            'id': trans.id,
            'date': trans.transaction_date,
            'item_list': json.loads(trans.items),  # Changed from 'items' to 'item_list'
            'subtotal': trans.subtotal,
            'tax': trans.tax,
            'total': trans.total,
            'payment_amount': trans.payment_amount,
            'change_amount': trans.change_amount,
            'payment_type': trans.payment_type
        })

    session.close()
    return render_template('transactions.html', transactions=transactions_data)

# ---------------- CSV DOWNLOAD ROUTE ----------------
@app.route('/transactions/download_csv')
def download_csv():
    session = TransactionSession()
    all_transactions = session.query(Transaction).order_by(Transaction.transaction_date.desc()).all()

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(['Transaction ID', 'Date', 'Items (JSON)', 'Subtotal', 'Tax', 'Total', 'Payment Amount', 'Change',
                     'Payment Type'])

    # Write data
    for trans in all_transactions:
        writer.writerow([
            trans.id,
            trans.transaction_date.strftime('%Y-%m-%d %H:%M:%S'),
            trans.items,  # JSON string in one cell
            f"{trans.subtotal:.2f}",
            f"{trans.tax:.2f}",
            f"{trans.total:.2f}",
            f"{trans.payment_amount:.2f}",
            f"{trans.change_amount:.2f}",
            trans.payment_type
        ])

    session.close()

    # Prepare file for download
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'transactions_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )


if __name__ == '__main__':
    app.run(debug=True)