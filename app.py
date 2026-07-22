import os
import smtplib
import string
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import stripe

app = Flask(__name__)
CORS(app)

# ==========================================
# CONFIGURATION & INITIALIZATION
# ==========================================
stripe.api_key = "sk_test_your_stripe_secret_key"

firebase_cred = credentials.Certificate("firebase-service-account.json")
firebase_admin.initialize_app(firebase_cred)
db = firestore.client()

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
gs_creds = ServiceAccountCredentials.from_json_keyfile_name("google-sheets-service-account.json", scope)
client = gspread.authorize(gs_creds)
sheet = client.open("2026 Gold Coast Open Registrations").sheet1

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "your_email@gmail.com"
SENDER_PASSWORD = "your_app_password"
ADMIN_EMAIL = "admin_email@gmail.com"

def send_email(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        text = msg.as_string()
        server.sendmail(SENDER_EMAIL, to_email, text)
        server.quit()
    except Exception as e:
        print(f"Failed to send email: {e}")

# ==========================================
# API ENDPOINTS: REGISTRATION & PAYMENT
# ==========================================
@app.route('/api/validate-discount/<code>', methods=['GET'])
def validate_discount(code):
    docs = list(db.collection('discount_codes').where('code', '==', code.upper()).where('used', '==', False).stream())
    if docs:
        return jsonify({"valid": True, "discountAmount": docs[0].to_dict()['discountAmount']})
    return jsonify({"valid": False, "discountAmount": 0})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    player_details = data.get('player')
    events = data.get('events')
    discount_code = data.get('discountCode', '').upper()
    
    # Calculate Total
    base_total = sum(float(event['price']) for event in events)
    ttq_levy = 5.00
    discount_amount = 0

    # Validate discount securely on backend
    if discount_code:
        docs = list(db.collection('discount_codes').where('code', '==', discount_code).where('used', '==', False).stream())
        if docs:
            discount_amount = float(docs[0].to_dict()['discountAmount'])

    final_total = (base_total + ttq_levy) - discount_amount
    if final_total < 0:
        final_total = 0

    registration_data = {
        "player": player_details,
        "events": events,
        "baseTotal": base_total,
        "ttqLevy": ttq_levy,
        "discountCode": discount_code,
        "discountAmount": discount_amount,
        "finalTotal": final_total,
        "paymentStatus": "Pending",
        "timestamp": firestore.SERVER_TIMESTAMP
    }
    
    doc_ref = db.collection('registrations').document()
    doc_ref.set(registration_data)
    registration_id = doc_ref.id

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': 'aud',
                        'unit_amount': int(final_total * 100),
                        'product_data': {
                            'name': '2026 Gold Coast Open Registration',
                        },
                    },
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=f"http://localhost:5000/success.html?session_id={{CHECKOUT_SESSION_ID}}&reg_id={registration_id}",
            cancel_url="http://localhost:5000/cancel.html",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"url": checkout_session.url, "registrationId": registration_id})

@app.route('/api/payment-success', methods=['POST'])
def payment_success():
    data = request.json
    registration_id = data.get('registrationId')
    
    db.collection('registrations').document(registration_id).update({"paymentStatus": "Paid"})
    
    doc = db.collection('registrations').document(registration_id).get()
    record = doc.to_dict()

    # Mark discount code as used if one was applied
    applied_code = record.get('discountCode')
    if applied_code:
        code_docs = list(db.collection('discount_codes').where('code', '==', applied_code).stream())
        if code_docs:
            db.collection('discount_codes').document(code_docs[0].id).update({"used": True})
    
    try:
        events_str = ", ".join([e['name'] for e in record['events']])
        row = [
            record['player']['firstName'], record['player']['lastName'], record['player']['email'],
            record['player']['phone'], record['player']['nationalId'], record['player']['club'],
            events_str, record['ttqLevy'], record['discountAmount'], record['finalTotal'], "Paid"
        ]
        sheet.append_row(row)
    except Exception as e:
        print(f"GSheet Error: {e}")

    email_body = f"""Hi {record['player']['firstName']},
    
Your registration for the 2026 Gold Coast Open Table Tennis Championships is confirmed!
    
Details:
Events: {events_str}
TTQ Levy: $5.00
Total Paid: ${record['finalTotal']}
    
See you at the tournament!"""
    send_email(record['player']['email'], "Tournament Registration Confirmation", email_body)
    
    admin_body = f"New Registration Paid:\nPlayer: {record['player']['firstName']} {record['player']['lastName']}\nTotal: ${record['finalTotal']}\nEvents: {events_str}"
    send_email(ADMIN_EMAIL, "New Tournament Registration", admin_body)
    
    return jsonify({"status": "success"})

# ==========================================
# API ENDPOINTS: ADMIN & DISCOUNTS
# ==========================================
@app.route('/api/admin/registrations', methods=['GET'])
def get_registrations():
    registrations = []
    docs = db.collection('registrations').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
    for doc in docs:
        data = doc.to_dict()
        data['id'] = doc.id
        registrations.append(data)
    return jsonify(registrations)

@app.route('/api/admin/registrations/<reg_id>', methods=['PUT'])
def update_registration(reg_id):
    data = request.json
    db.collection('registrations').document(reg_id).update(data)
    return jsonify({"status": "updated"})

@app.route('/api/admin/discount-codes', methods=['POST'])
def create_discount_code():
    data = request.json
    amount = float(data.get('amount', 5.0))
    # Generate an 8-character unique alphanumeric code
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    db.collection('discount_codes').add({
        "code": code,
        "discountAmount": amount,
        "used": False,
        "timestamp": firestore.SERVER_TIMESTAMP
    })
    return jsonify({"code": code, "amount": amount})

@app.route('/api/admin/discount-codes', methods=['GET'])
def get_discount_codes():
    codes = []
    docs = db.collection('discount_codes').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        codes.append(d)
    return jsonify(codes)

if __name__ == '__main__':
    app.run(port=5000, debug=True)