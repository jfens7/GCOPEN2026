import os
import string
import random
import re
from datetime import datetime
import pytz
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

def get_local_now_str():
    brisbane_tz = pytz.timezone('Australia/Brisbane')
    return datetime.now(brisbane_tz).strftime('%Y-%m-%d %H:%M:%S')

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

def generate_receipt_email(first_name, reg_id, events_str, partners_str, final_total, status):
    is_paid = ('Paid' in status) 
    paid_amount = float(final_total) if is_paid else 0.0
    owed_amount = 0.0 if is_paid else float(final_total)
    
    events_paid = max(0.0, paid_amount - 5.0) if paid_amount > 0 else 0.0

    owed_text = ""
    if owed_amount > 0:
        owed_text = "<p><em>*Note: You can pay your outstanding balance online at any time using the <strong>Update Registration</strong> tab on the website, or pay via Cash/EFT on arrival.</em></p>"

    return f"""<p>Hi {first_name},</p>
    <p>Your registration for the 2026 Gold Coast Open Table Tennis Championships has been recorded!</p>
    <p><strong>Registration Reference ID: {reg_id}</strong> (Please keep this safe. You will need it to update your entry).</p>
    <p><strong>Events:</strong> {events_str}<br>
    <strong>Doubles Partners:</strong> {partners_str}</p>
    
    <p><strong>Total Paid (Events):</strong> ${events_paid:.2f}<br>
    <strong>Total Owed:</strong> ${owed_amount:.2f}<br>
    <strong>TTQ Tournament Levy:</strong> $5.00</p>
    
    {owed_text}
    
    <p>Please contact the Tournament Director for any updates or changes to your entry via email - <a href="mailto:admin@goldcoasttabletennis.org.au">admin@goldcoasttabletennis.org.au</a></p>
    <p>See you at the tournament!</p>
    <p><strong>2026 Gold Coast Open</strong></p>"""

def lookup_rc_by_tta_id(tta_id):
    """Directly queries Ratings Central using the official PlayerTTA_ID parameter"""
    if not tta_id or str(tta_id).strip() in ["", "N/A", "None"]:
        return "N/A", "N/A"
    
    try:
        url = f"https://www.ratingscentral.com/PlayerList.php?PlayerTTA_ID={str(tta_id).strip()}&PlayerSport=1"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=6)
        soup = BeautifulSoup(resp.text, 'html.parser')
        table = soup.find('table', class_='Bordered')
        if table:
            tbody = table.find('tbody') or table
            for tr in tbody.find_all('tr'):
                tds = tr.find_all('td')
                rc_id, rating_str = "", ""
                if len(tds) == 5:
                    rating_str = tds[1].get_text(strip=True).split('±')[0].strip()
                    rc_id = tds[3].get_text(strip=True)
                elif len(tds) == 4:
                    rating_str = tds[0].get_text(strip=True).split('±')[0].strip()
                    rc_id = tds[2].get_text(strip=True)
                
                rating_str = re.sub(r'[^\d]', '', rating_str)
                if rc_id and rating_str.isdigit():
                    return rc_id, rating_str
    except Exception as e:
        print(f"RC TTA Lookup Error: {e}")
    
    return "N/A", "N/A"

def find_missing_rc(nat_id, first, last):
    """Fallback scraper by Name if TTA ID isn't linked on RC"""
    rc_id, rating = lookup_rc_by_tta_id(nat_id)
    if rc_id != "N/A":
        return rc_id, rating

    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        name_query = f"{last.strip()}, {first.strip()}"
        rc_url = f"https://www.ratingscentral.com/PlayerList.php?PlayerName={requests.utils.quote(name_query)}&PlayerSport=1"
        resp = requests.get(rc_url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        table = soup.find('table', class_='Bordered')
        if table:
            tbody = table.find('tbody') or table
            for tr in tbody.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) == 5:
                    r_str = re.sub(r'[^\d]', '', tds[1].get_text(strip=True).split('±')[0])
                    return tds[3].get_text(strip=True), r_str
                elif len(tds) == 4:
                    r_str = re.sub(r'[^\d]', '', tds[0].get_text(strip=True).split('±')[0])
                    return tds[2].get_text(strip=True), r_str
    except: pass
    return "N/A", "N/A"

# --- MASTER ROW GENERATOR (20 COLUMNS: A through T) ---
def sync_to_sheet(reg_id, record):
    """Generates the exact 20-column array and pushes it, guaranteeing clean column layout."""
    p = record.get('player', {})
    events_str = ", ".join([e['name'] for e in record.get('events', [])])
    partners_str = ", ".join([f"{k}: {v}" for k, v in record.get('doublesPartners', {}).items()])
    
    row_data = [
        reg_id, 
        p.get('firstName', ''), 
        p.get('lastName', ''), 
        p.get('email', ''),
        p.get('phone', ''), 
        p.get('dob', 'N/A'),
        p.get('gender', 'N/A'),
        p.get('nationalId', 'N/A'), 
        p.get('club', 'N/A'),
        p.get('rcId', 'N/A'), 
        p.get('rcRating', 'N/A'),
        str(p.get('neverPlayed', False)).upper(),
        events_str, 
        partners_str, 
        record.get('ttqLevy', 5.0), 
        record.get('discountAmount', 0),
        record.get('finalTotal', 0), 
        record.get('paymentStatus', 'Pending'),
        record.get('registeredAt', 'N/A'),
        record.get('paidAt', 'N/A')
    ]
    
    try:
        cell = sheet.find(reg_id)
        if cell:
            cell_list = sheet.range(f"A{cell.row}:T{cell.row}")
            for i, val in enumerate(row_data):
                cell_list[i].value = str(val)
            sheet.update_cells(cell_list)
        else:
            sheet.insert_row(row_data, 2)
    except Exception as e:
        print(f"GSheet Sync Error: {str(e)}")

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
    docs = list(db.collection('discount_codes').where(filter=FieldFilter('code', '==', code.upper())).stream())
    if docs:
        d = docs[0].to_dict()
        if not d.get('used', False) or d.get('isPermanent', False):
            return jsonify({"valid": True, "discountAmount": d['discountAmount']})
    return jsonify({"valid": False, "discountAmount": 0})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    player_details = data.get('player')
    events = data.get('events')
    discount_code = data.get('discountCode', '').upper()
    doubles_partners = data.get('doublesPartners', {})
    
    rc_val = player_details.get('rcId', '').strip()
    never_played = (rc_val.lower() == 'never played')
    
    existing_id = list(db.collection('registrations').where(filter=FieldFilter('player.nationalId', '==', player_details['nationalId'])).stream())
    existing_rc = []
    if rc_val and not never_played:
        existing_rc = list(db.collection('registrations').where(filter=FieldFilter('player.rcId', '==', rc_val)).stream())
    
    if len(existing_id) > 0 or len(existing_rc) > 0:
        return jsonify({"error": "A player with this National ID or Ratings Central ID is already registered."}), 400

    base_total = sum(float(event['price']) for event in events)
    ttq_levy = 5.00
    discount_amount = 0

    if discount_code:
        docs = list(db.collection('discount_codes').where(filter=FieldFilter('code', '==', discount_code)).stream())
        if docs:
            d = docs[0].to_dict()
            if not d.get('used', False) or d.get('isPermanent', False):
                discount_amount = float(d['discountAmount'])

    final_total = max(0.0, (base_total + ttq_levy) - discount_amount)
    player_details['neverPlayed'] = never_played

    # Ensure Gender is populated
    if not player_details.get('gender'):
        player_details['gender'] = 'N/A'

    # Auto-Fetch RC Rating using TTA ID lookup
    rc_rating = "N/A"
    if not never_played and player_details.get('nationalId'):
        found_rc, found_rating = lookup_rc_by_tta_id(player_details.get('nationalId'))
        if found_rc != "N/A":
            player_details['rcId'] = found_rc
            rc_rating = found_rating
    player_details['rcRating'] = rc_rating

    registered_at = get_local_now_str()
    paid_at = registered_at if final_total == 0 else "N/A"

    # INITIAL HISTORY ENTRY
    initial_history_entry = {
        "updateNumber": 0,
        "type": "Initial Registration",
        "timestamp": registered_at,
        "amountCharged": final_total,
        "paymentStatus": "Paid" if final_total == 0 else "Pending",
        "events": [e['name'] for e in events],
        "doublesPartners": doubles_partners,
        "notes": "Initial player registration"
    }

    registration_data = {
        "player": player_details,
        "events": events,
        "doublesPartners": doubles_partners,
        "baseTotal": base_total,
        "ttqLevy": ttq_levy,
        "discountCode": discount_code,
        "discountAmount": discount_amount,
        "originalTotal": final_total, # LOCKED ORIGINAL COST
        "finalTotal": final_total,
        "paymentStatus": "Paid" if final_total == 0 else "Pending",
        "registeredAt": registered_at,
        "paidAt": paid_at,
        "history": [initial_history_entry], # AUDIT TRAIL LOG
        "timestamp": firestore.SERVER_TIMESTAMP
    }
    
    doc_ref = db.collection('registrations').document()
    doc_ref.set(registration_data)
    registration_id = doc_ref.id

    sync_to_sheet(registration_id, registration_data)

    if data.get('payLater') or final_total == 0:
        if final_total == 0:
            return jsonify({"url": f"{BASE_URL}/api/payment-success?reg_id={registration_id}", "registrationId": registration_id})
        
        events_str = ", ".join([e['name'] for e in events])
        partners_str = ", ".join([f"{k}: {v}" for k, v in doubles_partners.items()])
        email_body = generate_receipt_email(player_details['firstName'], registration_id, events_str, partners_str, final_total, "Pending")
        send_email(player_details['email'], "Tournament Registration (Pending Payment)", email_body)
        
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
    session_id = request.args.get('session_id', 'N/A')
    
    if reg_id:
        paid_at = get_local_now_str()
        doc_ref = db.collection('registrations').document(reg_id)
        doc = doc_ref.get()
        if doc.exists:
            record = doc.to_dict()
            history = record.get('history', [])
            
            if history and len(history) > 0:
                history[0]['paymentStatus'] = 'Paid'
                history[0]['stripeSessionId'] = session_id
                history[0]['paidAt'] = paid_at
            
            doc_ref.update({
                "paymentStatus": "Paid",
                "paidAt": paid_at,
                "history": history
            })
            
            updated_record = doc_ref.get().to_dict()
            
            applied_code = updated_record.get('discountCode')
            if applied_code:
                code_docs = list(db.collection('discount_codes').where('code', '==', applied_code).stream())
                if code_docs:
                    doc_data = code_docs[0].to_dict()
                    if not doc_data.get('isPermanent', False):
                        db.collection('discount_codes').document(code_docs[0].id).update({"used": True})
            
            sync_to_sheet(reg_id, updated_record)

            events_str = ", ".join([e['name'] for e in updated_record.get('events', [])])
            partners_str = ", ".join([f"{k}: {v}" for k, v in updated_record.get('doublesPartners', {}).items()])
            email_body = generate_receipt_email(updated_record['player']['firstName'], reg_id, events_str, partners_str, updated_record['finalTotal'], "Paid")
            send_email(updated_record['player']['email'], "Tournament Registration Confirmation", email_body)

    return redirect(f"/success.html?reg_id={reg_id}")


# ==========================================
# UPDATE / BALANCE ENDPOINTS
# ==========================================
@app.route('/api/registration/lookup', methods=['POST'])
def lookup_reg():
    data = request.json
    email_input = data.get('email', '').strip().lower()
    nat_id_input = data.get('nationalId', '').strip()
    
    docs = db.collection('registrations').where(filter=FieldFilter('player.nationalId', '==', nat_id_input)).stream()
    registrations = []
    for doc in docs:
        doc_dict = doc.to_dict()
        doc_email = doc_dict.get('player', {}).get('email', '').strip().lower()
        if doc_email == email_input:
            registrations.append(doc_dict | {"id": doc.id})
            
    if not registrations:
        return jsonify({"error": "No registration found with this Email and TTA Member Number."}), 404
        
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
    new_final_total = max(0.0, (base_total + ttq_levy) - discount_amount)
        
    difference = round(new_final_total - old_final_total, 2)
    
    if difference <= 0:
        return jsonify({"error": "Your new total is less than or equal to what you already paid."}), 400
        
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
        
        # Calculate added and removed events for history logging
        old_event_names = [e['name'] for e in record.get('events', [])]
        new_event_names = [e['name'] for e in new_events]
        added_events = [e for e in new_event_names if e not in old_event_names]
        removed_events = [e for e in old_event_names if e not in new_event_names]

        doc_ref.update({
            "pendingUpdate": {
                "events": new_events,
                "doublesPartners": doubles_partners,
                "newFinalTotal": new_final_total,
                "difference": difference,
                "addedEvents": added_events,
                "removedEvents": removed_events
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
    session_id = request.args.get('session_id', 'N/A')
    
    if reg_id:
        doc_ref = db.collection('registrations').document(reg_id)
        doc = doc_ref.get()
        if doc.exists:
            record = doc.to_dict()
            paid_at = get_local_now_str()
            history = record.get('history', [])
            update_num = len(history)
            
            if 'pendingUpdate' in record:
                update_data = record['pendingUpdate']
                new_final = update_data['newFinalTotal']
                new_events = update_data['events']
                new_partners = update_data['doublesPartners']
                diff = update_data['difference']
                
                # Append Update Entry to Audit Log
                history.append({
                    "updateNumber": update_num,
                    "type": f"Update #{update_num} (Added Events)",
                    "timestamp": paid_at,
                    "amountPaid": diff,
                    "previousTotal": record.get('finalTotal', 0),
                    "newTotal": new_final,
                    "addedEvents": update_data.get('addedEvents', []),
                    "removedEvents": update_data.get('removedEvents', []),
                    "paymentStatus": "Paid",
                    "stripeSessionId": session_id
                })
                
                doc_ref.update({
                    "events": new_events,
                    "doublesPartners": new_partners,
                    "finalTotal": new_final,
                    "paymentStatus": "Paid",
                    "paidAt": paid_at,
                    "balanceDue": 0,
                    "history": history,
                    "pendingUpdate": firestore.DELETE_FIELD
                })
                
                updated_record = doc_ref.get().to_dict()
                sync_to_sheet(reg_id, updated_record)
                    
                events_str = ", ".join([e['name'] for e in new_events])
                partners_str = ", ".join([f"{k}: {v}" for k, v in new_partners.items()])
                email_body = generate_receipt_email(record['player']['firstName'], reg_id, events_str, partners_str, new_final, "Paid")
                send_email(record['player']['email'], "Registration Update Confirmed", email_body)
                
            elif float(record.get('balanceDue', 0)) > 0:
                old_total = float(record.get('finalTotal', 0))
                balance = float(record.get('balanceDue', 0))
                new_total = old_total + balance
                
                history.append({
                    "updateNumber": update_num,
                    "type": f"Update #{update_num} (Balance Payment)",
                    "timestamp": paid_at,
                    "amountPaid": balance,
                    "previousTotal": old_total,
                    "newTotal": new_total,
                    "paymentStatus": "Paid",
                    "stripeSessionId": session_id
                })
                
                doc_ref.update({
                    "finalTotal": new_total,
                    "paymentStatus": "Paid",
                    "paidAt": paid_at,
                    "balanceDue": 0,
                    "history": history
                })
                
                updated_record = doc_ref.get().to_dict()
                sync_to_sheet(reg_id, updated_record)

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
        if 'Paid' in d.get('paymentStatus', ''):
            total_revenue += float(d.get('finalTotal', 0))
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
    status = record.get('paymentStatus', 'Pending')
    
    email_body = generate_receipt_email(record['player']['firstName'], reg_id, events_str, partners_str, final_total, status)
    success = send_email(record['player']['email'], "Tournament Registration Confirmation (Resent)", email_body)
    
    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"error": "Failed to send email. Check Render logs."}), 500

@app.route('/api/admin/registrations/<reg_id>/resync', methods=['POST'])
def admin_resync(reg_id):
    doc_ref = db.collection('registrations').document(reg_id)
    doc = doc_ref.get()
    if not doc.exists:
        return jsonify({"error": "Registration not found"}), 404
        
    record = doc.to_dict()
    p = record.get('player', {})
    rc_val = p.get('rcId', '').strip()
    never_played = p.get('neverPlayed', False)
    
    if not never_played and (not rc_val or rc_val.lower() == 'n/a'):
        found_rc, found_rating = lookup_rc_by_tta_id(p.get('nationalId', ''))
        if found_rc == "N/A":
            found_rc, found_rating = find_missing_rc(p.get('nationalId', ''), p.get('firstName', ''), p.get('lastName', ''))
        if found_rc != "N/A":
            p['rcId'] = found_rc
            p['rcRating'] = found_rating
            doc_ref.update({
                "player.rcId": found_rc,
                "player.rcRating": found_rating
            })
            record['player']['rcId'] = found_rc
            record['player']['rcRating'] = found_rating

    sync_to_sheet(reg_id, record)
    return jsonify({"status": "success", "newRcId": p.get('rcId', rc_val)})

@app.route('/api/admin/bulk-fix-rc', methods=['POST'])
def bulk_fix_rc():
    """Iterates through all registrations, queries RC by TTA ID, updates missing RC IDs & Ratings, and rebuilds the Google Sheet"""
    docs = db.collection('registrations').stream()
    updated_count = 0
    
    for doc in docs:
        record = doc.to_dict()
        reg_id = doc.id
        p = record.get('player', {})
        
        tta_id = p.get('nationalId', '')
        never_played = p.get('neverPlayed', False)
        
        if not never_played and tta_id and tta_id != "N/A":
            found_rc, found_rating = lookup_rc_by_tta_id(tta_id)
            if found_rc == "N/A":
                found_rc, found_rating = find_missing_rc(tta_id, p.get('firstName', ''), p.get('lastName', ''))
                
            if found_rc != "N/A":
                db.collection('registrations').document(reg_id).update({
                    "player.rcId": found_rc,
                    "player.rcRating": found_rating
                })
                updated_count += 1

    # Rebuild Sheet
    all_docs = db.collection('registrations').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
    rows_data = []
    for doc in all_docs:
        rec = doc.to_dict()
        rid = doc.id
        pl = rec.get('player', {})
        e_str = ", ".join([e['name'] for e in rec.get('events', [])])
        pt_str = ", ".join([f"{k}: {v}" for k, v in rec.get('doublesPartners', {}).items()])
        
        row = [
            rid, pl.get('firstName',''), pl.get('lastName',''), pl.get('email',''),
            pl.get('phone',''), pl.get('dob','N/A'), pl.get('gender','N/A'),
            pl.get('nationalId','N/A'), pl.get('club','N/A'), pl.get('rcId','N/A'),
            pl.get('rcRating','N/A'), str(pl.get('neverPlayed', False)).upper(),
            e_str, pt_str, rec.get('ttqLevy', 5.0), rec.get('discountAmount', 0),
            rec.get('finalTotal', 0), rec.get('paymentStatus', 'Pending'),
            rec.get('registeredAt', 'N/A'), rec.get('paidAt', 'N/A')
        ]
        rows_data.append(row)
        
    sheet.batch_clear(["A2:T1000"])
    if rows_data:
        cell_list = sheet.range(f"A2:T{len(rows_data)+1}")
        flat_data = [item for sublist in rows_data for item in sublist]
        for i, val in enumerate(flat_data):
            cell_list[i].value = str(val)
        sheet.update_cells(cell_list)
        
    return jsonify({"status": "success", "updatedCount": updated_count, "totalRows": len(rows_data)})

@app.route('/api/admin/rebuild-sheet', methods=['POST'])
def rebuild_sheet():
    all_docs = db.collection('registrations').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
    rows_data = []
    for doc in all_docs:
        rec = doc.to_dict()
        rid = doc.id
        pl = rec.get('player', {})
        e_str = ", ".join([e['name'] for e in rec.get('events', [])])
        pt_str = ", ".join([f"{k}: {v}" for k, v in rec.get('doublesPartners', {}).items()])
        
        row = [
            rid, pl.get('firstName',''), pl.get('lastName',''), pl.get('email',''),
            pl.get('phone',''), pl.get('dob','N/A'), pl.get('gender','N/A'),
            pl.get('nationalId','N/A'), pl.get('club','N/A'), pl.get('rcId','N/A'),
            pl.get('rcRating','N/A'), str(pl.get('neverPlayed', False)).upper(),
            e_str, pt_str, rec.get('ttqLevy', 5.0), rec.get('discountAmount', 0),
            rec.get('finalTotal', 0), rec.get('paymentStatus', 'Pending'),
            rec.get('registeredAt', 'N/A'), rec.get('paidAt', 'N/A')
        ]
        rows_data.append(row)
        
    sheet.batch_clear(["A2:T1000"])
    if rows_data:
        cell_list = sheet.range(f"A2:T{len(rows_data)+1}")
        flat_data = [item for sublist in rows_data for item in sublist]
        for i, val in enumerate(flat_data):
            cell_list[i].value = str(val)
        sheet.update_cells(cell_list)
        
    return jsonify({"status": "success", "rows": len(rows_data)})

@app.route('/api/admin/manual-register', methods=['POST'])
def manual_register():
    data = request.json
    rc_val = data.get('rcId', 'N/A')
    never_played = data.get('neverPlayed', False)
    if never_played: rc_val = "Never Played"
    
    rc_rating = "N/A"
    if not never_played and data.get('nationalId'):
        found_rc, found_rating = lookup_rc_by_tta_id(data.get('nationalId'))
        if found_rc != "N/A":
            rc_val = found_rc
            rc_rating = found_rating

    registered_at = get_local_now_str()
    paid_at = registered_at if data.get('status') == 'Paid' else 'N/A'
    total_val = float(data.get('totalPaid', 0))

    initial_history = {
        "updateNumber": 0,
        "type": "Admin Manual Entry",
        "timestamp": registered_at,
        "amountCharged": total_val,
        "paymentStatus": data.get('status', 'Paid'),
        "events": [e['name'] for e in data.get('events', [])],
        "notes": "Added manually by admin"
    }

    registration_data = {
        "player": {
            "firstName": data.get('firstName', ''),
            "lastName": data.get('lastName', ''),
            "email": data.get('email', ''),
            "phone": data.get('phone', ''),
            "dob": data.get('dob', 'N/A'),
            "gender": data.get('gender', 'Male'),
            "nationalId": data.get('nationalId', 'N/A'),
            "rcId": rc_val,
            "rcRating": rc_rating,
            "club": data.get('club', 'N/A'),
            "neverPlayed": never_played
        },
        "events": data.get('events', []),
        "doublesPartners": {},
        "baseTotal": total_val,
        "ttqLevy": 0,
        "discountCode": "MANUAL",
        "discountAmount": 0,
        "originalTotal": total_val,
        "finalTotal": total_val,
        "paymentStatus": data.get('status', 'Paid'),
        "registeredAt": registered_at,
        "paidAt": paid_at,
        "history": [initial_history],
        "timestamp": firestore.SERVER_TIMESTAMP
    }
    
    doc_ref = db.collection('registrations').document()
    doc_ref.set(registration_data)
    sync_to_sheet(doc_ref.id, registration_data)
        
    return jsonify({"status": "success", "id": doc_ref.id})

@app.route('/api/admin/registrations/<reg_id>', methods=['PUT'])
def update_registration(reg_id):
    data = request.json
    doc_ref = db.collection('registrations').document(reg_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        return jsonify({"error": "Registration not found"}), 404
        
    record = doc.to_dict()
    history = record.get('history', [])
    now_str = get_local_now_str()

    update_payload = {}
    if 'player' in data:
        for k, v in data['player'].items(): 
            update_payload[f'player.{k}'] = v
            
    if 'events' in data: 
        update_payload['events'] = data['events']
    if 'doublesPartners' in data: 
        update_payload['doublesPartners'] = data['doublesPartners']
    if 'finalTotal' in data: 
        update_payload['finalTotal'] = data['finalTotal']
    if 'paymentStatus' in data: 
        update_payload['paymentStatus'] = data['paymentStatus']
        if 'Paid' in data['paymentStatus']:
            update_payload['paidAt'] = now_str

    # Append Admin Action to Audit History
    update_num = len(history)
    history.append({
        "updateNumber": update_num,
        "type": f"Admin Overwrite #{update_num}",
        "timestamp": now_str,
        "newTotal": data.get('finalTotal', record.get('finalTotal', 0)),
        "paymentStatus": data.get('paymentStatus', record.get('paymentStatus', 'Pending')),
        "notes": "Full overwrite updated via Admin Panel"
    })
    update_payload['history'] = history

    doc_ref.update(update_payload)
    updated_record = doc_ref.get().to_dict()
    sync_to_sheet(reg_id, updated_record)
    return jsonify({"status": "updated"})

@app.route('/api/admin/registrations/<reg_id>', methods=['DELETE'])
def delete_registration(reg_id):
    db.collection('registrations').document(reg_id).delete()
    try:
        cell = sheet.find(reg_id)
        if cell: sheet.delete_row(cell.row)
    except: pass
    return jsonify({"status": "deleted"})

@app.route('/api/admin/discount-codes', methods=['POST'])
def create_discount_code():
    data = request.json
    amount = float(data.get('amount', 5.0))
    is_perm = data.get('isPermanent', False)
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    db.collection('discount_codes').add({
        "code": code,
        "discountAmount": amount,
        "used": False,
        "isPermanent": is_perm,
        "timestamp": firestore.SERVER_TIMESTAMP
    })
    return jsonify({"code": code, "amount": amount, "isPermanent": is_perm})

@app.route('/api/admin/discount-codes', methods=['GET'])
def get_discount_codes():
    codes = []
    docs = db.collection('discount_codes').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        codes.append(d)
    return jsonify(codes)

@app.route('/api/admin/discount-codes/<doc_id>', methods=['PUT'])
def update_discount_code(doc_id):
    data = request.json
    db.collection('discount_codes').document(doc_id).update(data)
    return jsonify({"status": "updated"})

if __name__ == '__main__':
    print("Starting server on port 5000")
    app.run(host='0.0.0.0', port=5000)