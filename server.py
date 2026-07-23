import os
import string
import random
import re
from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.cloud.firestore_v1.base_query import FieldFilter
import stripe
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import resend

app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app)

# ==========================================
# CONFIGURATION & INITIALIZATION
# ==========================================
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
resend.api_key = os.getenv("RESEND_API_KEY", "")

raw_url = os.getenv("BASE_URL", "https://goldcoastopen.com").strip()
if not raw_url.startswith("http"):
    BASE_URL = f"https://{raw_url}"
else:
    BASE_URL = raw_url
BASE_URL = BASE_URL.rstrip("/") 

def get_secret_path(filename):
    if os.path.exists(f"/etc/secrets/{filename}"):
        return f"/etc/secrets/{filename}"
    return filename

# Firebase Setup
firebase_cred = credentials.Certificate(get_secret_path("gc-open-2026-firebase-adminsdk-fbsvc-efd2385c84.json"))
firebase_admin.initialize_app(firebase_cred)
db = firestore.client()

# Google Sheets Setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
gs_creds = ServiceAccountCredentials.from_json_keyfile_name(get_secret_path("gc-open-2026-260340b13caf.json"), scope)
client = gspread.authorize(gs_creds)
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1EJ5lEZs4eIkAUmYIbpssjhMTkJjWWsA5B2-cHO36gyA/edit?gid=0#gid=0").sheet1

SENDER_EMAIL = os.getenv("SENDER_EMAIL", "noreply@goldcoastopen.com")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "jakobwill7@gmail.com")

def send_email(to_email, subject, body):
    try:
        params: resend.Emails.SendParams = {
            "from": f"Gold Coast Open <{SENDER_EMAIL}>",
            "to": [to_email],
            "subject": subject,
            "html": body,
        }
        response = resend.Emails.send(params)
        print(f"Email sent successfully to {to_email}. Resend ID: {response}")
        return True
    except Exception as e:
        print(f"CRITICAL EMAIL ERROR - Failed to send to {to_email}: {str(e)}")
        return False

# ==========================================
# PAGE ROUTING
# ==========================================
@app.route('/')
def serve_home():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/registration')
def serve_registration():
    return send_from_directory(app.static_folder, 'register.html')

@app.route('/schedule')
def serve_schedule():
    return send_from_directory(app.static_folder, 'schedule.html')

@app.route('/admin')
def serve_admin():
    return send_from_directory(app.static_folder, 'admin.html')

@app.route('/success.html')
def serve_success():
    return send_from_directory(app.static_folder, 'success.html')

# ==========================================
# LOOKUP API ENDPOINTS
# ==========================================
@app.route('/api/national-id/search', methods=['GET'])
def search_national_id():
    name = request.args.get('name')
    if not name:
        return jsonify({"error": "Missing name"}), 400
    
    name_parts = name.strip().split(' ')
    first_name = name_parts[0] if len(name_parts) > 0 else ''
    last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            page = browser.new_page()
            
            page.goto('https://www.tabletennis.org.au/login')
            page.wait_for_selector('input[name="username"]')
            page.fill('input[name="username"]', 'jfensom3')
            page.fill('input[name="password"]', 'Pizza1200!')
            
            with page.expect_navigation():
                page.click('button#submit')
                
            page.goto('https://www.tabletennis.org.au/member-finder/')
            page.wait_for_selector('input[placeholder*="First name"]')
            
            page.fill('input[placeholder*="First name"]', first_name)
            if last_name:
                page.fill('input[placeholder*="last name"]', last_name)
                
            page.get_by_role("button", name="SEARCH").click()
            page.wait_for_timeout(2500)
            
            content = page.content()
            browser.close()
            
            soup = BeautifulSoup(content, 'html.parser')
            found_data = None
            
            for card in soup.find_all(class_='card'):
                text = card.get_text()
                if 'National Member ID:' in text:
                    match_id = re.search(r'National Member ID:\s*(\d+)', text)
                    match_state = re.search(r'State/Territory association\s*(Table Tennis [A-Za-z\s]+)', text)
                    if match_id:
                        found_data = {
                            "success": True,
                            "nationalId": match_id.group(1),
                            "state": match_state.group(1).strip() if match_state else "Unknown",
                            "status": "Active" if "Active" in text else "Unknown",
                            "rawText": re.sub(r'\s+', ' ', text).strip()
                        }
                        break
            
            if found_data:
                return jsonify(found_data)
            else:
                return jsonify({"error": "No matching National ID found."}), 404

    except Exception as e:
        if "Executable doesn't exist" in str(e):
            return jsonify({"error": "Playwright browser missing."}), 500
        return jsonify({"error": "Failed to search National ID", "details": str(e)}), 500


@app.route('/api/national-id/lookup-by-id', methods=['GET'])
def lookup_national_id_by_id():
    nat_id = request.args.get('id')
    if not nat_id:
        return jsonify({"error": "Missing National ID"}), 400
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            page = browser.new_page()
            
            page.goto('https://www.tabletennis.org.au/login')
            page.wait_for_selector('input[name="username"]')
            page.fill('input[name="username"]', 'jfensom3')
            page.fill('input[name="password"]', 'Pizza1200!')
            
            with page.expect_navigation():
                page.click('button#submit')
                
            page.goto('https://www.tabletennis.org.au/member-finder/')
            
            id_input = page.locator('input[placeholder*="National Member ID"]')
            if id_input.count() == 0:
                id_input = page.locator('input[type="text"]').first
                
            id_input.fill(str(nat_id))
            page.get_by_role("button", name="SEARCH").click()
            page.wait_for_timeout(2500)
            
            content = page.content()
            browser.close()
            
            soup = BeautifulSoup(content, 'html.parser')
            found_data = None
            
            for card in soup.find_all(class_='card'):
                text = card.get_text()
                if str(nat_id) in text:
                    name_tag = card.find('h4') or card.find('h5') or card.find('strong')
                    full_name_text = name_tag.get_text(strip=True) if name_tag else ""
                    
                    if not full_name_text:
                        lines = [line.strip() for line in text.split('\n') if line.strip()]
                        full_name_text = lines[0] if lines else ""
                    
                    first_name = ""
                    last_name = ""
                    if ',' in full_name_text:
                        parts = full_name_text.split(',')
                        last_name = parts[0].strip()
                        first_name = parts[1].strip()
                    else:
                        parts = full_name_text.split(' ')
                        first_name = parts[0].strip()
                        last_name = ' '.join(parts[1:]).strip()

                    born_match = re.search(r'Born\s*(\d{4})', text)
                    dob_year = born_match.group(1) if born_match else ""
                    match_state = re.search(r'State/Territory association\s*(Table Tennis [A-Za-z\s]+)', text)
                    
                    found_data = {
                        "success": True,
                        "firstName": first_name,
                        "lastName": last_name,
                        "dob": dob_year,
                        "nationalId": str(nat_id),
                        "state": match_state.group(1).strip() if match_state else "Unknown",
                    }
                    break
            
            if found_data:
                return jsonify(found_data)
            else:
                return jsonify({"error": f"No TTA member found with ID #{nat_id}."}), 404

    except Exception as e:
        return jsonify({"error": "Failed to search National ID", "details": str(e)}), 500


@app.route('/api/ratings-central/search', methods=['GET'])
def search_ratings_central():
    query = request.args.get('query')
    if not query:
        return jsonify({"error": "Missing search query"}), 400
    
    try:
        q_str = query.strip()
        if re.match(r'^\d+$', q_str):
            rc_url = f"https://www.ratingscentral.com/PlayerList.php?PlayerID={q_str}&PlayerSport=1"
        else:
            name_query = q_str.replace(',', '')
            name_parts = name_query.split()
            if len(name_parts) > 1 and ',' not in q_str:
                last = name_parts[-1]
                first = ' '.join(name_parts[:-1])
                name_query = f"{last}, {first}"
            else:
                name_query = q_str
            rc_url = f"https://www.ratingscentral.com/PlayerList.php?PlayerName={requests.utils.quote(name_query)}&PlayerSport=1"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(rc_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        players = []
        table = soup.find('table', class_='Bordered')
        if table:
            tbody = table.find('tbody') or table
            for tr in tbody.find_all('tr'):
                tds = tr.find_all('td')
                rating_str = ""
                name = ""
                player_id = ""
                last_event = ""
                
                if len(tds) == 5:
                    rating_str = tds[1].get_text(strip=True).split('±')[0].strip()
                    name = tds[2].get_text(strip=True)
                    player_id = tds[3].get_text(strip=True)
                    last_event = tds[4].get_text(strip=True)
                elif len(tds) == 4:
                    rating_str = tds[0].get_text(strip=True).split('±')[0].strip()
                    name = tds[1].get_text(strip=True)
                    player_id = tds[2].get_text(strip=True)
                    last_event = tds[3].get_text(strip=True)
                
                if player_id and rating_str and rating_str != "Unrated":
                    rating_str = re.sub(r'[\u200B-\u200D\uFEFF]', '', rating_str)
                    if rating_str.isdigit():
                        players.append({
                            "id": player_id,
                            "name": name,
                            "rating": int(rating_str),
                            "lastEvent": last_event
                        })
        return jsonify({"players": players, "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# REGISTRATION & PAYMENT API
# ==========================================
@app.route('/api/validate-discount/<code>', methods=['GET'])
def validate_discount(code):
    docs = list(db.collection('discount_codes').where(filter=FieldFilter('code', '==', code.upper())).where(filter=FieldFilter('used', '==', False)).stream())
    if docs:
        return jsonify({"valid": True, "discountAmount": docs[0].to_dict()['discountAmount']})
    return jsonify({"valid": False, "discountAmount": 0})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    player_details = data.get('player')
    events = data.get('events')
    discount_code = data.get('discountCode', '').upper()
    doubles_partners = data.get('doublesPartners', {})
    
    existing_id = list(db.collection('registrations').where(filter=FieldFilter('player.nationalId', '==', player_details['nationalId'])).stream())
    existing_rc = []
    rc_id = player_details.get('rcId', '').strip()
    if rc_id:
        existing_rc = list(db.collection('registrations').where(filter=FieldFilter('player.rcId', '==', rc_id)).stream())
    
    if len(existing_id) > 0 or len(existing_rc) > 0:
        return jsonify({"error": "A player with this National ID or Ratings Central ID is already registered."}), 400

    base_total = sum(float(event['price']) for event in events)
    ttq_levy = 5.00
    discount_amount = 0

    if discount_code:
        docs = list(db.collection('discount_codes').where(filter=FieldFilter('code', '==', discount_code)).where(filter=FieldFilter('used', '==', False)).stream())
        if docs:
            discount_amount = float(docs[0].to_dict()['discountAmount'])

    final_total = (base_total + ttq_levy) - discount_amount
    if final_total < 0:
        final_total = 0

    registration_data = {
        "player": player_details,
        "events": events,
        "doublesPartners": doubles_partners,
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
        events_str = ", ".join([e['name'] for e in events])
        partners_str = ", ".join([f"{k}: {v}" for k, v in doubles_partners.items()])
        
        row = [
            registration_id, player_details['firstName'], player_details['lastName'], player_details['email'],
            player_details['phone'], player_details['nationalId'], player_details['club'],
            player_details.get('rcId', ''), events_str, partners_str, 
            ttq_levy, discount_amount, final_total, "Pending"
        ]
        
        sheet.insert_row(row, 2)
    except Exception as e:
        print(f"GSheet Insert Error: {e}")

    if data.get('payLater') or final_total == 0:
        if final_total == 0:
            return jsonify({"url": f"{BASE_URL}/api/payment-success?reg_id={registration_id}", "registrationId": registration_id})
        
        events_str = ", ".join([e['name'] for e in events])
        partners_str = ", ".join([f"{k}: {v}" for k, v in doubles_partners.items()])
        email_body = f"""<p>Hi {player_details['firstName']},</p>
        <p>Your registration for the 2026 Gold Coast Open Table Tennis Championships has been saved!</p>
        <p><strong>Registration Reference ID: {registration_id}</strong> (Please keep this safe)</p>
        <p><strong>Events:</strong> {events_str}<br>
        <strong>Doubles Partners:</strong> {partners_str}<br>
        <strong>Total Due:</strong> ${final_total}</p>
        <p>Please remember to pay your outstanding balance on arrival (Cash or EFT).</p>
        <p>See you at the tournament!</p>"""
        send_email(player_details['email'], "Tournament Registration (Pay Later)", email_body)
        
        admin_body = f"<p>New PAY LATER Registration:<br>Player: {player_details['firstName']} {player_details['lastName']}<br>Ref ID: {registration_id}<br>Total Due: ${final_total}<br>Events: {events_str}</p>"
        send_email(ADMIN_EMAIL, "New Tournament Registration (Pay Later)", admin_body)
        
        return jsonify({"url": f"{BASE_URL}/success.html?reg_id={registration_id}", "registrationId": registration_id})

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'aud',
                    'unit_amount': int(final_total * 100),
                    'product_data': {'name': '2026 Gold Coast Open Registration'},
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{BASE_URL}/api/payment-success?session_id={{CHECKOUT_SESSION_ID}}&reg_id={registration_id}",
            cancel_url=f"{BASE_URL}/registration",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"url": checkout_session.url, "registrationId": registration_id})

@app.route('/api/payment-success', methods=['GET'])
def payment_success():
    reg_id = request.args.get('reg_id')
    if reg_id:
        db.collection('registrations').document(reg_id).update({"paymentStatus": "Paid"})
        doc = db.collection('registrations').document(reg_id).get()
        if doc.exists:
            record = doc.to_dict()
            applied_code = record.get('discountCode')
            if applied_code:
                code_docs = list(db.collection('discount_codes').where('code', '==', applied_code).stream())
                if code_docs:
                    db.collection('discount_codes').document(code_docs[0].id).update({"used": True})
            
            try:
                cell = sheet.find(reg_id)
                if cell:
                    sheet.update_cell(cell.row, 14, "Paid") 
            except Exception as e:
                print(f"GSheet Update Error: {e}")

            events_str = ", ".join([e['name'] for e in record['events']])
            partners_str = ", ".join([f"{k}: {v}" for k, v in record.get('doublesPartners', {}).items()])

            email_body = f"""<p>Hi {record['player']['firstName']},</p>
            <p>Your registration for the 2026 Gold Coast Open Table Tennis Championships is confirmed!</p>
            <p><strong>Registration Reference ID: {reg_id}</strong> (Please keep this safe)</p>
            <p><strong>Events:</strong> {events_str}<br>
            <strong>Doubles Partners:</strong> {partners_str}<br>
            <strong>TTQ Levy:</strong> $5.00<br>
            <strong>Total Paid:</strong> ${record['finalTotal']}</p>
            <p>See you at the tournament!</p>"""
            send_email(record['player']['email'], "Tournament Registration Confirmation", email_body)
            
            admin_body = f"<p>New Paid Registration:<br>Player: {record['player']['firstName']} {record['player']['lastName']}<br>Ref ID: {reg_id}<br>Total: ${record['finalTotal']}<br>Events: {events_str}<br>Partners: {partners_str}</p>"
            send_email(ADMIN_EMAIL, "New Tournament Registration", admin_body)

    return redirect(f"/success.html?reg_id={reg_id}")


# ==========================================
# UPDATE / BALANCE ENDPOINTS
# ==========================================

@app.route('/api/registration/lookup', methods=['POST'])
def lookup_reg():
    data = request.json
    email_input = data.get('email', '').strip().lower()
    dob = data.get('dob', '').strip()
    
    docs = db.collection('registrations').where(filter=FieldFilter('player.dob', '==', dob)).stream()
    registrations = []
    for doc in docs:
        doc_dict = doc.to_dict()
        doc_email = doc_dict.get('player', {}).get('email', '').strip().lower()
        if doc_email == email_input:
            registrations.append(doc_dict | {"id": doc.id})
            
    if not registrations:
        return jsonify({"error": "No registration found with this Email and DOB."}), 404
        
    return jsonify(registrations[0])

@app.route('/api/registration/update-checkout', methods=['POST'])
def update_checkout():
    data = request.json
    reg_id = data.get('reg_id')
    new_events = data.get('events')
    doubles_partners = data.get('doublesPartners', {})
    
    doc_ref = db.collection('registrations').document(reg_id)
    doc = doc_ref.get()
    if not doc.exists:
        return jsonify({"error": "Registration not found."}), 404
        
    record = doc.to_dict()
    
    old_final_total = float(record.get('finalTotal', 0))
    base_total = sum(float(event['price']) for event in new_events)
    ttq_levy = 5.00
    discount_amount = float(record.get('discountAmount', 0))
    new_final_total = (base_total + ttq_levy) - discount_amount
    if new_final_total < 0:
        new_final_total = 0
        
    difference = new_final_total - old_final_total
    
    if difference <= 0:
        return jsonify({"error": "Your new total is less than or equal to what you already paid. If you are removing events and require a refund, please contact the admin."}), 400
        
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'aud',
                    'unit_amount': int(difference * 100),
                    'product_data': {'name': '2026 Gold Coast Open - Registration Update'},
                },
                'quantity': 1,
            }],
            mode='payment',
            metadata={'reg_id': reg_id, 'update_type': 'events_update'},
            success_url=f"{BASE_URL}/api/update-success?session_id={{CHECKOUT_SESSION_ID}}&reg_id={reg_id}",
            cancel_url=f"{BASE_URL}/update.html",
        )
        
        doc_ref.update({
            "pendingUpdate": {
                "events": new_events,
                "doublesPartners": doubles_partners,
                "newFinalTotal": new_final_total,
                "difference": difference
            }
        })
        
        return jsonify({"url": checkout_session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/registration/pay-balance', methods=['POST'])
def pay_balance():
    data = request.json
    reg_id = data.get('reg_id')
    
    doc_ref = db.collection('registrations').document(reg_id)
    doc = doc_ref.get()
    if not doc.exists:
        return jsonify({"error": "Registration not found."}), 404
        
    record = doc.to_dict()
    balance = float(record.get('balanceDue', 0))
    
    if balance <= 0:
        return jsonify({"error": "No outstanding balance."}), 400
        
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'aud',
                    'unit_amount': int(balance * 100),
                    'product_data': {'name': '2026 Gold Coast Open - Outstanding Balance'},
                },
                'quantity': 1,
            }],
            mode='payment',
            metadata={'reg_id': reg_id, 'update_type': 'balance_payment'},
            success_url=f"{BASE_URL}/api/update-success?session_id={{CHECKOUT_SESSION_ID}}&reg_id={reg_id}",
            cancel_url=f"{BASE_URL}/update.html",
        )
        return jsonify({"url": checkout_session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/update-success', methods=['GET'])
def update_success():
    reg_id = request.args.get('reg_id')
    
    if reg_id:
        doc_ref = db.collection('registrations').document(reg_id)
        doc = doc_ref.get()
        if doc.exists:
            record = doc.to_dict()
            
            if 'pendingUpdate' in record:
                update_data = record['pendingUpdate']
                new_final = update_data['newFinalTotal']
                new_events = update_data['events']
                new_partners = update_data['doublesPartners']
                
                doc_ref.update({
                    "events": new_events,
                    "doublesPartners": new_partners,
                    "finalTotal": new_final,
                    "paymentStatus": "Paid",
                    "balanceDue": 0,
                    "pendingUpdate": firestore.DELETE_FIELD
                })
                
                try:
                    cell = sheet.find(reg_id)
                    if cell:
                        events_str = ", ".join([e['name'] for e in new_events])
                        partners_str = ", ".join([f"{k}: {v}" for k, v in new_partners.items()])
                        sheet.update_cell(cell.row, 9, events_str)
                        sheet.update_cell(cell.row, 10, partners_str)
                        sheet.update_cell(cell.row, 13, new_final)
                        sheet.update_cell(cell.row, 14, "Paid")
                except Exception as e:
                    print("Sheet update error:", e)
                    
                email_body = f"<p>Your registration update has been confirmed! Your new total is ${new_final}.</p>"
                send_email(record['player']['email'], "Registration Update Confirmed", email_body)
                
            elif float(record.get('balanceDue', 0)) > 0:
                old_total = float(record.get('finalTotal', 0))
                balance = float(record.get('balanceDue', 0))
                
                doc_ref.update({
                    "finalTotal": old_total + balance,
                    "paymentStatus": "Paid",
                    "balanceDue": 0
                })
                
                try:
                    cell = sheet.find(reg_id)
                    if cell:
                        sheet.update_cell(cell.row, 13, old_total + balance)
                        sheet.update_cell(cell.row, 14, "Paid")
                except Exception as e:
                    print("Sheet update error:", e)
                    
                email_body = "<p>Your outstanding balance has been paid successfully.</p>"
                send_email(record['player']['email'], "Balance Payment Confirmed", email_body)

    return redirect(f"/success.html?reg_id={reg_id}&updated=true")


# ==========================================
# ADMIN ENDPOINTS
# ==========================================
@app.route('/api/admin/stats', methods=['GET'])
def get_admin_stats():
    docs = db.collection('registrations').stream()
    total_revenue = 0
    total_players = 0
    pending_payments = 0
    
    for doc in docs:
        d = doc.to_dict()
        total_players += 1
        if d.get('paymentStatus') == 'Paid':
            total_revenue += d.get('finalTotal', 0)
        else:
            pending_payments += 1
            
    return jsonify({
        "totalRevenue": total_revenue,
        "totalPlayers": total_players,
        "pendingPayments": pending_payments
    })

@app.route('/api/admin/registrations', methods=['GET'])
def get_registrations():
    registrations = []
    docs = db.collection('registrations').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
    for doc in docs:
        data = doc.to_dict()
        data['id'] = doc.id
        registrations.append(data)
    return jsonify(registrations)

@app.route('/api/admin/registrations/<reg_id>/resend-email', methods=['POST'])
def admin_resend_email(reg_id):
    doc_ref = db.collection('registrations').document(reg_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        return jsonify({"error": "Registration not found"}), 404
        
    record = doc.to_dict()
    
    events_str = ", ".join([e['name'] for e in record.get('events', [])])
    partners_str = ", ".join([f"{k}: {v}" for k, v in record.get('doublesPartners', {}).items()])
    final_total = record.get('finalTotal', 0)
    
    email_body = f"""<p>Hi {record['player']['firstName']},</p>
    <p>Your registration for the 2026 Gold Coast Open Table Tennis Championships is confirmed!</p>
    <p><strong>Registration Reference ID: {reg_id}</strong> (Please keep this safe)</p>
    <p><strong>Events:</strong> {events_str}<br>
    <strong>Doubles Partners:</strong> {partners_str}<br>
    <strong>Total Paid / Due:</strong> ${final_total}</p>
    <p>See you at the tournament!</p>"""
    
    success = send_email(record['player']['email'], "Tournament Registration Confirmation (Resent)", email_body)
    
    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"error": "Failed to send email. Check Render logs."}), 500

@app.route('/api/admin/manual-register', methods=['POST'])
def manual_register():
    data = request.json
    
    registration_data = {
        "player": {
            "firstName": data.get('firstName', ''),
            "lastName": data.get('lastName', ''),
            "email": data.get('email', ''),
            "phone": data.get('phone', ''),
            "nationalId": data.get('nationalId', 'N/A'),
            "rcId": data.get('rcId', 'N/A'),
            "club": data.get('club', 'N/A')
        },
        "events": [{"name": data.get('eventsText', '')}],
        "doublesPartners": {},
        "baseTotal": float(data.get('totalPaid', 0)),
        "ttqLevy": 0,
        "discountCode": "MANUAL",
        "discountAmount": 0,
        "finalTotal": float(data.get('totalPaid', 0)),
        "paymentStatus": data.get('status', 'Paid'),
        "timestamp": firestore.SERVER_TIMESTAMP
    }
    
    doc_ref = db.collection('registrations').document()
    doc_ref.set(registration_data)
    reg_id = doc_ref.id

    try:
        row = [
            reg_id, data.get('firstName', ''), data.get('lastName', ''), data.get('email', ''),
            data.get('phone', ''), data.get('nationalId', 'N/A'), data.get('club', 'N/A'),
            data.get('rcId', 'N/A'), data.get('eventsText', ''), "", 
            0, 0, float(data.get('totalPaid', 0)), data.get('status', 'Paid')
        ]
        sheet.insert_row(row, 2)
    except Exception as e:
        print(f"Manual GSheet Insert Error: {e}")
        
    return jsonify({"status": "success", "id": reg_id})

@app.route('/api/admin/registrations/<reg_id>', methods=['PUT'])
def update_registration(reg_id):
    data = request.json
    db.collection('registrations').document(reg_id).update(data)
    
    try:
        cell = sheet.find(reg_id)
        if cell:
            if 'paymentStatus' in data:
                sheet.update_cell(cell.row, 14, data['paymentStatus'])
            if 'finalTotal' in data:
                sheet.update_cell(cell.row, 13, data['finalTotal'])
            if 'events' in data:
                events_str = ", ".join([e['name'] for e in data['events']])
                sheet.update_cell(cell.row, 9, events_str)
    except Exception as e:
        print(f"GSheet Update Error: {e}")
            
    return jsonify({"status": "updated"})

@app.route('/api/admin/registrations/<reg_id>', methods=['DELETE'])
def delete_registration(reg_id):
    try:
        db.collection('registrations').document(reg_id).delete()
        try:
            cell = sheet.find(reg_id)
            if cell:
                try:
                    sheet.delete_row(cell.row)
                except AttributeError:
                    sheet.delete_rows(cell.row)
        except Exception as e:
            print(f"GSheet Delete Error: {e}")
            
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/discount-codes', methods=['POST'])
def create_discount_code():
    data = request.json
    amount = float(data.get('amount', 5.0))
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
    print("Starting server on port 5000")
    app.run(host='0.0.0.0', port=5000)