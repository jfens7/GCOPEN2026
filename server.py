"""
=========================================================================================
GOLD COAST OPEN 2026 - MASTER TOURNAMENT SERVER
=========================================================================================

This server handles all backend operations for the Gold Coast Open, including:
1. Stripe Payment Processing & Webhooks
2. Firebase / Firestore Integration
3. Google Sheets Two-Way Sync
4. Ratings Central & TTA National ID Scrapers
5. Playwright-powered Zermelo FTP Sync (Bypassing InfinityFree Security)
6. Gemini 3.1 Pro AI Data Extraction for Native Draws
7. Manual Zermelo HTML Fallback Parsing Engine

Architecture: Flask + Gunicorn
API Standard: RESTful JSON
AI Engine: Gemini 3.1 Pro (google-genai)

=========================================================================================
"""

import os
import sys
import string
import random
import re
import hashlib
import json
import logging
import traceback
from datetime import datetime
import pytz

# Web & API Framework
from flask import Flask
from flask import request
from flask import jsonify
from flask import send_from_directory
from flask import redirect
from flask import make_response
from flask_cors import CORS

# Firebase & Database
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# Google Sheets API
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Integrations
import stripe
import requests
from bs4 import BeautifulSoup
from bs4 import Tag
from playwright.sync_api import sync_playwright
import resend

# AI Extraction Data Models
try:
    from google import genai
    from pydantic import BaseModel
    from pydantic import Field
    from typing import List
    from typing import Optional
    from typing import Dict
    from typing import Any
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("WARNING: google-genai or pydantic not installed. AI Parsing disabled.")

# ==============================================================================
# 1. LOGGING & ENVIRONMENT SETUP
# ==============================================================================

class CustomFormatter(logging.Formatter):
    """
    Custom logging formatter for detailed Render logs.
    Provides color-coded terminal output for easier debugging during live events.
    """
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: grey + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset
    }

    def format(self, record):
        """Formats the log record with the appropriate color codes."""
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

logger = logging.getLogger("GCOpenServer")
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
ch.setFormatter(CustomFormatter())

if not logger.handlers:
    logger.addHandler(ch)

logger.info("Initializing Gold Coast Open Server Boot Sequence...")

app = Flask(
    __name__, 
    static_folder='public', 
    static_url_path=''
)

CORS(
    app, 
    resources={r"/api/*": {"origins": "*"}}
)

# API Keys Initialization
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
resend.api_key = os.getenv("RESEND_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# URL Configurations
ZERMELO_HOST_URL = os.getenv(
    "ZERMELO_HOST_URL", 
    "http://gcopen-draws.infinityfreeapp.com"
).rstrip("/")

raw_url = os.getenv(
    "BASE_URL", 
    "https://goldcoastopen.com"
).strip()

if not raw_url.startswith("http"):
    BASE_URL = f"https://{raw_url}"
else:
    BASE_URL = raw_url

BASE_URL = BASE_URL.rstrip("/") 

# Bot Evasion Headers for Zermelo/RatingsCentral Scraping
SCRAPER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1"
}

def get_secret_path(filename: str) -> str:
    """
    Safely resolves file paths for Render's secret mount points vs local development.
    Render mounts secret files into the /etc/secrets/ directory.
    """
    render_path = f"/etc/secrets/{filename}"
    
    if os.path.exists(render_path):
        logger.debug(f"Resolved secret path at Render mount: {render_path}")
        return render_path
        
    logger.debug(f"Resolved secret path at local root: {filename}")
    return filename

# ==============================================================================
# 2. FIREBASE & GOOGLE SHEETS INITIALIZATION
# ==============================================================================

def initialize_firebase():
    """
    Initializes the Firebase Admin SDK.
    Returns the Firestore database client object.
    """
    try:
        cred_path = get_secret_path("gc-open-2026-firebase-adminsdk-fbsvc-efd2385c84.json")
        firebase_cred = credentials.Certificate(cred_path)
        
        firebase_admin.initialize_app(firebase_cred)
        client = firestore.client()
        
        logger.info("Firebase Firestore initialized successfully.")
        return client
        
    except Exception as e:
        logger.critical(f"Failed to initialize Firebase: {e}")
        logger.critical(traceback.format_exc())
        return None

def initialize_google_sheets():
    """
    Initializes Google Sheets API clients for Master tracking and Zermelo sync sheets.
    Returns a tuple of (main_sheet, zermelo_sheet).
    """
    try:
        scope = [
            "https://spreadsheets.google.com/feeds", 
            "https://www.googleapis.com/auth/drive"
        ]
        
        gs_cred_path = get_secret_path("gc-open-2026-260340b13caf.json")
        gs_creds = ServiceAccountCredentials.from_json_keyfile_name(gs_cred_path, scope)
        g_client = gspread.authorize(gs_creds)
        
        main_sheet = g_client.open_by_url(
            "https://docs.google.com/spreadsheets/d/1EJ5lEZs4eIkAUmYIbpssjhMTkJjWWsA5B2-cHO36gyA/edit?gid=0#gid=0"
        ).sheet1
        
        z_sheet = g_client.open_by_key(
            "1Rb3HHQxw8qubkA4FNjGxJ6-05Ifjl37C0own4E-ldTE"
        ).sheet1
        
        logger.info("Google Sheets connections established successfully.")
        return main_sheet, z_sheet
        
    except Exception as e:
        logger.critical(f"Failed to initialize Google Sheets: {e}")
        logger.critical(traceback.format_exc())
        return None, None

# Execute connections
db = initialize_firebase()
sheet, zermelo_sheet = initialize_google_sheets()

# ==============================================================================
# 3. CONSTANTS & EVENT METADATA
# ==============================================================================

SENDER_EMAIL = os.getenv(
    "SENDER_EMAIL", 
    "noreply@goldcoastopen.com"
)

ADMIN_EMAIL = os.getenv(
    "ADMIN_EMAIL", 
    "jakobwill7@gmail.com"
)

# Core tournament configuration parameters
DOUBLES_EVENT_IDS = [
    3, 
    4, 
    21, 
    33, 
    34
]

RATING_LIMITS = {
    6: 1700, 
    7: 1400, 
    18: 1200, 
    19: 1000, 
    20: 800
}

# Extensive internal mapping dictionary for event validation
EVENT_CATALOG = {
    1: "Event #1: Men's Open Singles",
    2: "Event #2: Women's Open Singles",
    3: "Event #3: Men's Open Doubles",
    4: "Event #4: Women's Open Doubles",
    5: "Event #5: Para Open Singles",
    6: "Event #6: Under 1700 Singles",
    7: "Event #7: Under 1400 Singles",
    8: "Event #8: Under 19 Boy's Singles",
    9: "Event #9: Under 19 Girl's Singles",
    10: "Event #10: Under 17 Boy's Singles",
    11: "Event #11: Under 17 Girl's Singles",
    12: "Event #12: Under 15 Boy's Singles",
    13: "Event #13: Under 15 Girl's Singles",
    14: "Event #14: Under 13 Boy's Singles",
    15: "Event #15: Under 13 Girl's Singles",
    16: "Event #16: Under 11 Boy's Singles",
    17: "Event #17: Under 11 Girl's Singles",
    18: "Event #18: Under 1200 Singles",
    19: "Event #19: Under 1000 Singles",
    20: "Event #20: Under 800 Singles",
    21: "Event #21: Open Rating Doubles",
    22: "Event #22: Over 30 Men's Singles",
    23: "Event #23: Over 30 Women's Singles",
    24: "Event #24: Over 40 Men's Singles",
    25: "Event #25: Over 40 Women's Singles",
    26: "Event #26: Over 50 Men's Singles",
    27: "Event #27: Over 50 Women's Singles",
    28: "Event #28: Over 60 Men's Singles",
    29: "Event #29: Over 60 Women's Singles",
    30: "Event #30: Over 70 Men's Singles",
    31: "Event #31: Over 70 Women's Singles",
    32: "Event #32: Over 80 Singles",
    33: "Event #33: Veteran Women's Doubles",
    34: "Event #34: Veteran Men's Doubles",
    # Extended placeholders to ensure robustness
    35: "Event #35: Mixed Open Doubles",
    36: "Event #36: Under 21 Men's Singles",
    37: "Event #37: Under 21 Women's Singles",
    38: "Event #38: Under 1800 Singles",
    39: "Event #39: Under 1600 Singles",
    40: "Event #40: Under 1300 Singles"
}

# ==============================================================================
# 4. PYDANTIC SCHEMAS FOR GEMINI 3.1 PRO STRUCTURED OUTPUT
# ==============================================================================

if GEMINI_AVAILABLE:
    class PlayerStat(BaseModel):
        """Schema for an individual player's group stage statistics."""
        name: str = Field(
            description="The full name of the player or pair."
        )
        wins: int = Field(
            description="Number of wins in the group stage."
        )
        losses: int = Field(
            description="Number of losses in the group stage."
        )
        pts: int = Field(
            description="Total points accumulated in the group."
        )
        advance: bool = Field(
            description="True if the player advances to knockout, False otherwise."
        )

    class GroupInfo(BaseModel):
        """Schema representing a single round-robin group."""
        name: str = Field(
            description="Name of the group, e.g., 'Group 1' or 'Group A'."
        )
        players: List[PlayerStat] = Field(
            description="List of players inside this specific group."
        )

    class MatchInfo(BaseModel):
        """Schema representing a single match in a knockout bracket."""
        p1: str = Field(
            description="Name of Player 1. If empty or missing, use 'TBD' or 'BYE'."
        )
        s1: str = Field(
            description="Score or sets won by Player 1."
        )
        p2: str = Field(
            description="Name of Player 2. If empty or missing, use 'TBD' or 'BYE'."
        )
        s2: str = Field(
            description="Score or sets won by Player 2."
        )
        winner: int = Field(
            description="0 if undecided, 1 if p1 won, 2 if p2 won."
        )

    class KnockoutRound(BaseModel):
        """Schema representing a specific round in an elimination bracket."""
        roundName: str = Field(
            description="Name of the round, e.g., 'Quarter Finals' or 'Round of 16'."
        )
        matches: List[MatchInfo] = Field(
            description="Matches occurring within this round."
        )

    class EventDraw(BaseModel):
        """Master schema representing an entire tournament event's draw logic."""
        eventName: str = Field(
            description="The exact title of the event being extracted."
        )
        hasGroups: bool = Field(
            description="True if a round-robin group stage exists."
        )
        hasKnockout: bool = Field(
            description="True if a knockout/elimination bracket exists."
        )
        groups: List[GroupInfo] = Field(
            description="Array of all group structures."
        )
        knockout: List[KnockoutRound] = Field(
            description="Array of all knockout rounds."
        )

# ==============================================================================
# 5. CORE UTILITY FUNCTIONS
# ==============================================================================

def get_local_now_str() -> str:
    """
    Returns the current timestamp localized to the Brisbane timezone.
    Used for all database timestamping to ensure consistency.
    """
    try:
        brisbane_tz = pytz.timezone('Australia/Brisbane')
        return datetime.now(brisbane_tz).strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        logger.error(f"Timezone resolution failed: {e}")
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def evaluate_eligibility_warnings(rating_str: str, events: list) -> list:
    """
    Validates a player's official Ratings Central rating against 
    the maximum rating limits defined for specific events.
    """
    warnings = []
    
    if str(rating_str).isdigit():
        r_val = int(rating_str)
        
        for ev in events:
            ev_id = ev.get('id')
            
            if ev_id in RATING_LIMITS:
                max_allowed = RATING_LIMITS[ev_id]
                
                if r_val > max_allowed:
                    warn_msg = f"Rating {r_val} exceeds limit of {max_allowed} for {ev.get('name')}"
                    warnings.append(warn_msg)
                    logger.warning(warn_msg)
                    
    return warnings

def send_email(to_email: str, subject: str, body: str) -> bool:
    """
    Dispatches transactional HTML emails utilizing the Resend API.
    Handles network errors gracefully without crashing the main thread.
    """
    if not resend.api_key:
        logger.warning(f"Resend API key missing. Email to {to_email} aborted.")
        return False
        
    try:
        params: resend.Emails.SendParams = {
            "from": f"Gold Coast Open <{SENDER_EMAIL}>",
            "to": [to_email],
            "subject": subject,
            "html": body,
        }
        
        response = resend.Emails.send(params)
        logger.info(f"Email dispatched to {to_email}. Transaction ID: {response}")
        return True
        
    except Exception as e:
        logger.error(f"Email dispatch failed for {to_email}: {e}")
        logger.error(traceback.format_exc())
        return False

def generate_receipt_email(
    first_name: str, 
    reg_id: str, 
    events_str: str, 
    partners_str: str, 
    final_total: float, 
    status: str, 
    late_fee: float = 0.0
) -> str:
    """
    Constructs a highly styled, professional HTML email receipt 
    for players upon successful registration or update.
    """
    is_paid = ('Paid' in status) 
    paid_amount = float(final_total) if is_paid else 0.0
    owed_amount = 0.0 if is_paid else float(final_total)
    
    events_paid = max(0.0, paid_amount - 5.0 - late_fee) if paid_amount > 0 else 0.0

    owed_text = ""
    if owed_amount > 0:
        owed_text = """
        <div style="background-color: #FEF2F2; border-left: 4px solid #EF4444; padding: 15px; margin-top: 20px;">
            <p style="margin: 0; color: #991B1B;">
                <em>*Note: please pay your outstanding balance online at any time using the 
                <strong>Update Registration</strong> tab on the website. Make sure to pay 
                your balance by the close of entries. Any outstanding online payments will 
                incur a $10 late admin fee per event. Thanks for your understanding!</em>
            </p>
        </div>
        """

    late_fee_text = ""
    if late_fee > 0:
        late_fee_text = f"<br><strong>Late Entry Surcharge:</strong> ${late_fee:.2f}"

    html_template = f"""
    <div style="font-family: Arial, sans-serif; color: #334155; line-height: 1.6; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #E2E8F0; border-radius: 8px;">
        
        <h2 style="color: #1E3A8A; border-bottom: 2px solid #D97706; padding-bottom: 10px;">
            Registration Confirmed
        </h2>
        
        <p>Hi {first_name},</p>
        <p>Your registration for the 2026 Gold Coast Open Table Tennis Championships has been recorded!</p>
        
        <div style="background: #F1F5F9; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <p style="margin: 0 0 10px 0;">
                <strong>Registration Reference ID:</strong> 
                <span style="font-family: monospace; font-size: 16px; background: #E2E8F0; padding: 4px 8px; border-radius: 4px; font-weight: bold; color: #1E3A8A;">
                    {reg_id}
                </span>
            </p>
            <p style="margin: 0; font-size: 13px; color: #64748B;">
                Please keep this ID safe. You will need it to update your entry or pay outstanding balances.
            </p>
        </div>
        
        <h3 style="color: #1E3A8A; margin-bottom: 10px;">Entry Details</h3>
        <p style="margin-top: 0;"><strong>Events:</strong><br> {events_str}</p>
        <p><strong>Doubles Partners:</strong><br> {partners_str}</p>
        
        <div style="border-top: 1px solid #E2E8F0; margin: 20px 0; padding-top: 20px;">
            <p style="margin: 5px 0; display: flex; justify-content: space-between;">
                <span>Total Paid (Events):</span> <strong>${events_paid:.2f}</strong>
            </p>
            <p style="margin: 5px 0; display: flex; justify-content: space-between;">
                <span>TTQ Tournament Levy:</span> <strong>$5.00</strong>
            </p>
            {f'<p style="margin: 5px 0; display: flex; justify-content: space-between;"><span>Late Entry Surcharge:</span> <strong>${late_fee:.2f}</strong></p>' if late_fee > 0 else ''}
            
            <h3 style="color: #D97706; margin: 15px 0 5px 0; display: flex; justify-content: space-between; border-top: 1px dashed #CBD5E1; padding-top: 10px;">
                <span>Total Owed:</span> <strong>${owed_amount:.2f}</strong>
            </h3>
        </div>
        
        {owed_text}
        
        <p style="margin-top: 30px;">
            Please contact the Tournament Director for any updates or changes to your entry via email - 
            <a href="mailto:admin@goldcoasttabletennis.org.au" style="color: #1E3A8A; font-weight: bold;">
                admin@goldcoasttabletennis.org.au
            </a>
        </p>
        <p>See you at the tournament!</p>
        <p><strong>2026 Gold Coast Open Organizing Committee</strong></p>
    </div>
    """
    
    return html_template

# ==============================================================================
# 6. EXTERNAL SCRAPING & ID LOOKUP FUNCTIONS
# ==============================================================================

def lookup_rc_by_tta_id(tta_id: str) -> tuple:
    """
    Scrapes Ratings Central directory to find an RC ID and rating using a TTA National ID.
    Returns a tuple: (RC_ID, Rating)
    """
    if not tta_id or str(tta_id).strip() in ["", "N/A", "None"]:
        return "N/A", "N/A"
        
    try:
        url = f"https://www.ratingscentral.com/PlayerList.php?PlayerTTA_ID={str(tta_id).strip()}&PlayerSport=1"
        resp = requests.get(url, headers=SCRAPER_HEADERS, timeout=8)
        
        if resp.status_code != 200:
            logger.warning(f"RC lookup returned status code {resp.status_code}")
            return "N/A", "N/A"
            
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
                    logger.info(f"Successfully found RC ID {rc_id} for TTA ID {tta_id}")
                    return rc_id, rating_str
                    
    except requests.exceptions.RequestException as re_exc:
        logger.error(f"Network error during RC lookup: {re_exc}")
    except Exception as e:
        logger.error(f"Unexpected error in RC TTA Lookup: {e}")
        
    return "N/A", "N/A"

def find_missing_rc(nat_id: str, first: str, last: str) -> tuple:
    """
    Fallback scraping method.
    If TTA ID lookup fails, this performs a rigorous text-based search 
    using the player's First and Last Name.
    """
    rc_id, rating = lookup_rc_by_tta_id(nat_id)
    if rc_id != "N/A":
        return rc_id, rating

    try:
        logger.info(f"TTA ID lookup failed for {first} {last}, attempting name fallback...")
        
        name_query = f"{last.strip()}, {first.strip()}"
        rc_url = f"https://www.ratingscentral.com/PlayerList.php?PlayerName={requests.utils.quote(name_query)}&PlayerSport=1"
        
        resp = requests.get(rc_url, headers=SCRAPER_HEADERS, timeout=8)
        
        if resp.status_code != 200:
            return "N/A", "N/A"
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        table = soup.find('table', class_='Bordered')
        
        if table:
            tbody = table.find('tbody') or table
            for tr in tbody.find_all('tr'):
                tds = tr.find_all('td')
                
                if len(tds) == 5:
                    r_str = re.sub(r'[^\d]', '', tds[1].get_text(strip=True).split('±')[0])
                    found_id = tds[3].get_text(strip=True)
                    logger.info(f"Name fallback successful. Found ID: {found_id}")
                    return found_id, r_str
                    
                elif len(tds) == 4:
                    r_str = re.sub(r'[^\d]', '', tds[0].get_text(strip=True).split('±')[0].strip())
                    found_id = tds[2].get_text(strip=True)
                    logger.info(f"Name fallback successful. Found ID: {found_id}")
                    return found_id, r_str
                    
    except Exception as e:
        logger.warning(f"Fallback Name Search Failed: {e}")
        
    return "N/A", "N/A"

def sync_to_sheet(reg_id: str, record: dict):
    """
    Executes a Google Sheets API call to sync database records to the spreadsheet.
    Finds the exact row by ID and overwrites, or appends a new row if absent.
    """
    if sheet is None:
        logger.error("Cannot sync to sheet, client is uninitialized.")
        return
        
    p = record.get('player', {})
    events = record.get('events', [])
    
    events_str = ", ".join([e['name'] for e in events])
    partners_str = ", ".join([f"{k}: {v}" for k, v in record.get('doublesPartners', {}).items()])
    
    total_events = len(events)
    doubles_count = sum(1 for e in events if e.get('id') in DOUBLES_EVENT_IDS)
    singles_count = total_events - doubles_count
    
    warnings = record.get('eligibilityWarnings', [])
    warnings_str = " | ".join(warnings) if warnings else ""

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
        record.get('paidAt', 'N/A'),
        singles_count, 
        doubles_count, 
        total_events, 
        warnings_str
    ]
    
    try:
        cell = sheet.find(reg_id)
        if cell:
            cell_list = sheet.range(f"A{cell.row}:X{cell.row}")
            for i, val in enumerate(row_data):
                cell_list[i].value = val
            sheet.update_cells(cell_list, value_input_option='USER_ENTERED')
            logger.info(f"Google Sheet updated row for {reg_id}")
        else:
            sheet.append_row(row_data, value_input_option='USER_ENTERED')
            logger.info(f"Google Sheet appended new row for {reg_id}")
            
    except gspread.exceptions.APIError as g_err:
        logger.error(f"GSpread API Rate Limit / Error for {reg_id}: {g_err}")
    except Exception as e:
        logger.error(f"GSheet Sync Fatal Error for {reg_id}: {str(e)}")


# ==============================================================================
# 7. ZERMELO MANUAL FALLBACK PARSER (NO AI)
# ==============================================================================

class ZermeloManualParser:
    """
    A robust, defensive BeautifulSoup parsing engine designed specifically 
    to extract data from Zermelo's unique, legacy 1990s HTML tables.
    Used strictly as a fallback mechanism if Gemini AI fails.
    """
    
    @staticmethod
    def parse_event_html(event_name: str, html_content: str) -> dict:
        """
        Parses the raw HTML and constructs a JSON structure matching the EventDraw schema.
        Handles broken tags, missing columns, and arbitrary table nesting.
        """
        logger.info(f"Executing Manual Zermelo Parse for {event_name}")
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
        except Exception as soup_err:
            logger.error(f"BS4 failed to load HTML: {soup_err}")
            return {"eventName": event_name, "hasGroups": False, "hasKnockout": False, "groups": [], "knockout": []}
            
        result = {
            "eventName": event_name,
            "hasGroups": False,
            "hasKnockout": False,
            "groups": [],
            "knockout": []
        }
        
        tables = soup.find_all('table')
        if not tables:
            logger.warning(f"No tables found in HTML for {event_name}")
            return result
            
        current_group = None
        
        for table in tables:
            try:
                # Zermelo group tables usually have a specific header structure
                is_group_table = False
                first_row = table.find('tr')
                
                if first_row:
                    header_text = first_row.get_text().upper()
                    
                    if "GROUP" in header_text or "POOL" in header_text:
                        is_group_table = True
                        result["hasGroups"] = True
                        
                        group_name_match = re.search(r'(GROUP\s+\w+|POOL\s+\w+)', header_text, re.IGNORECASE)
                        g_name = group_name_match.group(1) if group_name_match else f"Group {len(result['groups'])+1}"
                        
                        current_group = {
                            "name": g_name, 
                            "players": []
                        }
                        result['groups'].append(current_group)
                        
                if is_group_table and current_group:
                    rows = table.find_all('tr')
                    for row in rows[1:]: # Skip the group header
                        cols = row.find_all('td')
                        if len(cols) >= 4:
                            try:
                                # Standard Zermelo structure: Name, Wins, Losses, Points, Place
                                name_col = cols[0].get_text(strip=True)
                                
                                # Ignore spacer rows, bye rows, and nested table anomalies
                                if name_col and name_col.lower() != 'name' and "bye" not in name_col.lower():
                                    
                                    wins_match = re.search(r'\d+', cols[1].get_text())
                                    wins = int(wins_match[0]) if wins_match else 0
                                    
                                    losses_match = re.search(r'\d+', cols[2].get_text())
                                    losses = int(losses_match[0]) if losses_match else 0
                                    
                                    pts_match = re.search(r'\d+', cols[3].get_text())
                                    pts = int(pts_match[0]) if pts_match else 0
                                    
                                    # Advance logic based on place (usually top 1 or 2)
                                    advance = False
                                    if len(cols) > 4:
                                        place_text = cols[4].get_text(strip=True)
                                        if place_text in ['1', '2']:
                                            advance = True
                                            
                                    current_group['players'].append({
                                        "name": name_col,
                                        "wins": wins,
                                        "losses": losses,
                                        "pts": pts,
                                        "advance": advance
                                    })
                                    
                            except Exception as parse_e:
                                logger.debug(f"Row skipped in manual group parse: {parse_e}")
                                
                else:
                    # If not a group table, analyze for Knockout Bracket characteristics
                    text_content = table.get_text().lower()
                    
                    if "final" in text_content or "round of" in text_content:
                        result["hasKnockout"] = True
                        
                        # Knockout parsing in raw BS4 is highly brittle for Zermelo.
                        # We use naive row pairing extraction.
                        rows = table.find_all('tr')
                        current_round_matches = []
                        
                        for i in range(len(rows) - 1):
                            tds1 = rows[i].find_all('td')
                            tds2 = rows[i+1].find_all('td')
                            
                            if len(tds1) > 0 and len(tds2) > 0:
                                p1_text = tds1[0].get_text(strip=True)
                                p2_text = tds2[0].get_text(strip=True)
                                
                                if p1_text and p2_text and len(p1_text) > 3 and len(p2_text) > 3:
                                    
                                    # Determine winner based on bold tags (Zermelo uses <b> for winners)
                                    winner = 0
                                    if tds1[0].find('b'): 
                                        winner = 1
                                    elif tds2[0].find('b'): 
                                        winner = 2
                                    
                                    current_round_matches.append({
                                        "p1": p1_text.replace('BYE', '').strip() or 'BYE',
                                        "s1": "0", 
                                        "p2": p2_text.replace('BYE', '').strip() or 'BYE',
                                        "s2": "0",
                                        "winner": winner
                                    })
                                    
                        if current_round_matches:
                            result['knockout'].append({
                                "roundName": "Elimination Round",
                                "matches": current_round_matches
                            })
                            
            except Exception as table_err:
                logger.error(f"Error parsing specific table: {table_err}")
                continue
                
        logger.info(f"Manual parsing completed for {event_name}. Extracted {len(result['groups'])} groups.")
        return result


# ==============================================================================
# 8. FLASK PAGE ROUTING & HEALTH CHECKS
# ==============================================================================

@app.route('/')
def serve_home(): 
    logger.info("Serving Homepage Index")
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/registration')
def serve_registration(): 
    logger.info("Serving Registration Page")
    return send_from_directory(app.static_folder, 'register.html')

@app.route('/schedule')
def serve_schedule(): 
    logger.info("Serving Schedule Portal")
    return send_from_directory(app.static_folder, 'schedule.html')

@app.route('/admin')
def serve_admin(): 
    logger.info("Serving Secure Admin Portal")
    return send_from_directory(app.static_folder, 'admin.html')

@app.route('/success.html')
def serve_success(): 
    logger.info("Serving Payment Success Gateway")
    return send_from_directory(app.static_folder, 'success.html')

@app.route('/live-draws.html')
def serve_live_draws():
    logger.info("Serving Native Live Draws Application")
    return send_from_directory(app.static_folder, 'live-draws.html')

@app.route('/draws.html')
def serve_official_draws():
    logger.info("Serving Official Zermelo Draws Page")
    return send_from_directory(app.static_folder, 'draws.html')

@app.route('/results/<path:filename>')
def serve_zermelo_results(filename):
    """
    Proxies raw Zermelo HTML exactly as it appears, bypassing InfinityFree.
    """
    try:
        target_url = f"{ZERMELO_HOST_URL}/{filename}"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = browser.new_context(user_agent=SCRAPER_HEADERS["User-Agent"])
            page = context.new_page()
            page.goto(target_url)
            page.wait_for_timeout(3000) # Bypass aes.js
            html_content = page.content()
            browser.close()
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Ensure relative links map back to our proxy
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if href.lower().endswith('.htm') or href.lower().endswith('.html'):
                a_tag['href'] = f"/results/{href}"
                
        return str(soup)

    except Exception as e:
        logger.error(f"Zermelo Proxy Error: {e}")
        return "<h2>Tournament Server Offline</h2><p>Unable to connect to the live draw server.</p>", 500

@app.route('/draws')
def serve_draws_redirect(): 
    logger.info("Redirecting Legacy /draws endpoint to /live-draws.html")
    return redirect('/live-draws.html')

# -- SYSTEM DIAGNOSTICS & STATUS --
@app.route('/api/health', methods=['GET'])
def health_check():
    """Simple ping endpoint for uptime monitoring and load balancers."""
    return jsonify({
        "status": "healthy", 
        "timestamp": get_local_now_str(),
        "service": "Gold Coast Open API"
    }), 200

@app.route('/api/admin/diagnostics', methods=['GET'])
def run_diagnostics():
    """Returns detailed connection status for all external APIs."""
    status = {
        "firebase": "disconnected",
        "google_sheets": "disconnected",
        "stripe": "configured" if stripe.api_key else "missing_key",
        "resend": "configured" if resend.api_key else "missing_key",
        "gemini_ai": "configured" if GEMINI_AVAILABLE and GEMINI_API_KEY else "disabled_or_missing",
        "timestamp": get_local_now_str()
    }
    
    # Test DB Link
    if db is not None:
        try:
            db.collection('settings').document('health').set({"last_ping": get_local_now_str()})
            status["firebase"] = "connected"
        except Exception as e:
            status["firebase"] = f"error: {str(e)}"
            
    # Test Sheets Link
    if sheet is not None and zermelo_sheet is not None:
        try:
            sheet.row_values(1)
            status["google_sheets"] = "connected"
        except Exception as e:
            status["google_sheets"] = f"error: {str(e)}"
            
    logger.info(f"System diagnostics requested. Configuration status: {status}")
    return jsonify(status), 200


# ==============================================================================
# 9. MEMBER DIRECTORY & NATIONAL ID API
# ==============================================================================
@app.route('/api/national-id/search', methods=['GET'])
def search_national_id():
    """Searches TTA directory dynamically by First and Last name using Playwright."""
    name = request.args.get('name')
    if not name: 
        logger.warning("National ID Search aborted: Missing name parameter in payload.")
        return jsonify({"error": "Missing name"}), 400
    
    name_parts = name.strip().split(' ')
    first_name = name_parts[0] if len(name_parts) > 0 else ''
    last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
    
    logger.info(f"Executing TTA Name Search for: {first_name} {last_name}")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            page = browser.new_page(user_agent=SCRAPER_HEADERS["User-Agent"])
            
            page.goto('https://www.tabletennis.org.au/')
            page.wait_for_timeout(3000)
            
            try:
                # Target RevSports popup modald
                close_btn = page.locator('.close, button[aria-label="Close"], .ui-dialog-titlebar-close, text="×"').first
                if close_btn.is_visible():
                    close_btn.click(force=True)
                else:
                    viewport = page.viewport_size
                    if viewport:
                        page.mouse.click(viewport['width'] / 2, viewport['height'] / 2)
            except Exception as inner_e:
                logger.debug(f"Popup dismissal failed (ignoring): {inner_e}")
            
            page.wait_for_timeout(1000)
            page.goto('https://www.tabletennis.org.au/login')
            
            page.wait_for_selector('input[name="username"]')
            page.fill('input[name="username"]', 'jfensom3')
            page.fill('input[name="password"]', 'Pizza1200!')
            
            with page.expect_navigation(): 
                page.click('button#submit')
                
            page.goto('https://www.tabletennis.org.au/member-finder/')
            
            page.get_by_placeholder(re.compile("First name", re.IGNORECASE)).wait_for(state="visible")
            page.get_by_placeholder(re.compile("First name", re.IGNORECASE)).fill(first_name)
            
            if last_name: 
                page.get_by_placeholder(re.compile("Last name", re.IGNORECASE)).fill(last_name)
                
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
                            "status": "Active" if "Active" in text else "Unknown"
                        }
                        break
                        
            if found_data: 
                logger.info(f"TTA Match Found successfully: {found_data['nationalId']}")
                return jsonify(found_data)
            
            logger.info("No matching TTA records found for query.")
            return jsonify({"error": "No matching National ID found."}), 404
            
    except Exception as e:
        logger.error(f"Playwright Execution Failed in search_national_id: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/national-id/lookup-by-id', methods=['GET'])
def lookup_national_id_by_id():
    """Validates an exact TTA Member ID and returns user profile details."""
    nat_id = request.args.get('id')
    if not nat_id: 
        logger.warning("National ID Lookup aborted: Missing ID parameter.")
        return jsonify({"error": "Missing National ID"}), 400
        
    logger.info(f"Executing TTA Exact Lookup for ID: {nat_id}")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            page = browser.new_page(user_agent=SCRAPER_HEADERS["User-Agent"])
            
            page.goto('https://www.tabletennis.org.au/')
            page.wait_for_timeout(3000)
            
            try:
                close_btn = page.locator('.close, button[aria-label="Close"], .ui-dialog-titlebar-close, text="×"').first
                if close_btn.is_visible():
                    close_btn.click(force=True)
            except Exception:
                pass
            
            page.wait_for_timeout(1000)
            page.goto('https://www.tabletennis.org.au/login')
            
            page.wait_for_selector('input[name="username"]')
            page.fill('input[name="username"]', 'jfensom3')
            page.fill('input[name="password"]', 'Pizza1200!')
            
            with page.expect_navigation(): 
                page.click('button#submit')
                
            page.goto('https://www.tabletennis.org.au/member-finder/')
            
            id_input = page.get_by_placeholder(re.compile("National Member ID", re.IGNORECASE))
            if id_input.count() == 0: 
                id_input = page.locator('input[type="text"]').first
                
            id_input.wait_for(state="visible")
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
                    
                    first_name, last_name = "", ""
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
                logger.info(f"Lookup successful for ID {nat_id}: {first_name} {last_name}")
                return jsonify(found_data)
                
            logger.info(f"Lookup failed. No TTA member found with ID #{nat_id}.")
            return jsonify({"error": f"No TTA member found with ID #{nat_id}."}), 404
            
    except Exception as e:
        logger.error(f"Failed to lookup National ID {nat_id}: {traceback.format_exc()}")
        return jsonify({"error": "Failed to search National ID", "details": str(e)}), 500

@app.route('/api/ratings-central/search', methods=['GET'])
def search_ratings_central():
    """Queries the external Ratings Central directory by name or ID."""
    query = request.args.get('query')
    
    if not query: 
        logger.warning("RC Search aborted: Missing query parameter.")
        return jsonify({"error": "Missing search query"}), 400
        
    logger.info(f"Executing Ratings Central query: '{query}'")
    
    try:
        q_str = query.strip()
        
        if re.match(r'^\d+$', q_str):
            rc_url = f"https://www.ratingscentral.com/PlayerList.php?PlayerID={q_str}&PlayerSport=1"
        else:
            name_query = q_str.replace(',', '')
            name_parts = name_query.split()
            if len(name_parts) > 1 and ',' not in q_str:
                name_query = f"{name_parts[-1]}, {' '.join(name_parts[:-1])}"
            else:
                name_query = q_str
                
            rc_url = f"https://www.ratingscentral.com/PlayerList.php?PlayerName={requests.utils.quote(name_query)}&PlayerSport=1"
        
        resp = requests.get(rc_url, headers=SCRAPER_HEADERS, timeout=10)
        
        if resp.status_code != 200:
            logger.error(f"Ratings Central returned HTTP {resp.status_code}")
            return jsonify({"error": "External service unavailable"}), 502
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        players = []
        table = soup.find('table', class_='Bordered')
        
        if table:
            tbody = table.find('tbody') or table
            for tr in tbody.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) >= 4:
                    rating_str = tds[1].get_text(strip=True).split('±')[0].strip() if len(tds) == 5 else tds[0].get_text(strip=True).split('±')[0].strip()
                    name = tds[2].get_text(strip=True) if len(tds) == 5 else tds[1].get_text(strip=True)
                    player_id = tds[3].get_text(strip=True) if len(tds) == 5 else tds[2].get_text(strip=True)
                    rating_str = re.sub(r'[^\d]', '', rating_str)
                    
                    if player_id and rating_str.isdigit():
                        players.append({
                            "id": player_id, 
                            "name": name, 
                            "rating": int(rating_str)
                        })
                        
        logger.info(f"RC query returned {len(players)} players.")
        return jsonify({
            "players": players, 
            "status": "success"
        })
        
    except requests.exceptions.RequestException as re_exc:
        logger.error(f"Network error searching Ratings Central: {re_exc}")
        return jsonify({"error": "Network timeout contacting Ratings Central."}), 504
    except Exception as e:
        logger.error(f"General error searching Ratings Central: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/validate-discount/<code>', methods=['GET'])
def validate_discount(code):
    """Validates a promotional code string against the Firestore database."""
    logger.info(f"Validating discount code attempt: {code}")
    
    if not db:
        return jsonify({"valid": False, "discountAmount": 0, "error": "DB disconnected"}), 500
        
    try:
        docs = list(db.collection('discount_codes').where(filter=FieldFilter('code', '==', code.upper())).stream())
        
        if docs:
            d = docs[0].to_dict()
            if not d.get('used', False) or d.get('isPermanent', False):
                
                logger.info(f"Code {code} is valid. Type: {d.get('discountType')}, Amount: {d.get('discountAmount')}")
                return jsonify({
                    "valid": True, 
                    "discountAmount": d.get('discountAmount', 0),
                    "discountType": d.get('discountType', 'dollar')
                })
                
        logger.info(f"Code {code} is invalid, fully redeemed, or expired.")
        return jsonify({
            "valid": False, 
            "discountAmount": 0, 
            "discountType": "dollar"
        })
        
    except Exception as e:
        logger.error(f"Error validating discount code: {e}")
        return jsonify({"valid": False, "discountAmount": 0, "error": "Internal error"}), 500

# ==============================================================================
# 10. CHECKOUT & REGISTRATION API
# ==============================================================================
@app.route('/api/register', methods=['POST'])
def register():
    """Handles new player registrations, Stripe session creation, and email dispatch."""
    if not request.is_json:
        return jsonify({"error": "Payload must be strictly valid JSON."}), 400
        
    data = request.json
    player_details = data.get('player')
    events = data.get('events', [])
    discount_code = data.get('discountCode', '').upper()
    doubles_partners = data.get('doublesPartners', {})
    
    if not player_details or not isinstance(player_details, dict):
        return jsonify({"error": "Invalid or missing player data object."}), 400
        
    if not events or len(events) == 0:
        return jsonify({"error": "You must select at least one event to register."}), 400
    
    first_name = player_details.get('firstName', 'Unknown')
    last_name = player_details.get('lastName', 'Unknown')
    logger.info(f"Processing new registration pipeline for: {first_name} {last_name}")
    
    rc_val = player_details.get('rcId', '').strip()
    never_played = (rc_val.lower() == 'never played')
    
    # 1. Duplication Security Check
    try:
        existing_id = list(db.collection('registrations').where(filter=FieldFilter('player.nationalId', '==', player_details.get('nationalId'))).stream())
        existing_rc = []
        if rc_val and not never_played:
            existing_rc = list(db.collection('registrations').where(filter=FieldFilter('player.rcId', '==', rc_val)).stream())
        
        if len(existing_id) > 0 or len(existing_rc) > 0:
            logger.warning(f"Registration block: Duplicate player detected for {first_name} {last_name}")
            return jsonify({"error": "A player with this National ID or Ratings Central ID is already registered."}), 400
    except Exception as e:
        logger.error(f"Duplicate validation failed: {e}")

    # 2. Financial Modeling
    try:
        base_total = sum(float(event.get('price', 0)) for event in events)
    except ValueError:
        return jsonify({"error": "Invalid price value detected in event payload array."}), 400
        
    ttq_levy = 5.00
    discount_amount = 0.0
    late_fee = 0.0

    # 3. Discount Application Logic
    if discount_code:
        docs = list(db.collection('discount_codes').where(filter=FieldFilter('code', '==', discount_code)).stream())
        if docs:
            d = docs[0].to_dict()
            if not d.get('used', False) or d.get('isPermanent', False):
                dtype = d.get('discountType', 'dollar')
                dval = float(d.get('discountAmount', 0))
                
                if dtype == 'percent':
                    discount_amount = (base_total + ttq_levy + late_fee) * (dval / 100.0)
                else:
                    discount_amount = dval

    discount_amount = round(discount_amount, 2)
    final_total = round(max(0.0, (base_total + ttq_levy + late_fee) - discount_amount), 2)
    
    player_details['neverPlayed'] = never_played
    if not player_details.get('gender'):
        player_details['gender'] = 'N/A'

    # 4. Ratings Sync & Validation
    rc_rating = "N/A"
    if not never_played and player_details.get('nationalId'):
        found_rc, found_rating = lookup_rc_by_tta_id(player_details.get('nationalId'))
        if found_rc != "N/A":
            player_details['rcId'] = found_rc
            rc_rating = found_rating
            
    player_details['rcRating'] = rc_rating

    # 5. Timestamps & Immutable History Generation
    registered_at = get_local_now_str()
    paid_at = registered_at if final_total == 0 else "N/A"
    
    if data.get('payLater'):
        pending_reason = "Pay Later Selected"
    else:
        pending_reason = "Abandoned Checkout"
        
    if final_total == 0:
        pending_reason = "N/A"

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

    warnings = evaluate_eligibility_warnings(rc_rating, events)

    # 6. Database Object Payload Assembly
    registration_data = {
        "player": player_details,
        "events": events,
        "doublesPartners": doubles_partners,
        "baseTotal": base_total,
        "ttqLevy": ttq_levy,
        "lateFee": late_fee,
        "discountCode": discount_code,
        "discountAmount": discount_amount,
        "originalTotal": final_total,
        "finalTotal": final_total,
        "balanceDue": final_total if final_total > 0 else 0,
        "paymentStatus": "Paid" if final_total == 0 else "Pending",
        "pendingReason": pending_reason,
        "eligibilityWarnings": warnings,
        "registeredAt": registered_at,
        "paidAt": paid_at,
        "history": [initial_history_entry],
        "timestamp": firestore.SERVER_TIMESTAMP
    }
    
    try:
        doc_ref = db.collection('registrations').document()
        doc_ref.set(registration_data)
        registration_id = doc_ref.id
        logger.info(f"Firebase document committed successfully. Ref ID: {registration_id}")
    except Exception as e:
        logger.error(f"Firebase document creation failed: {e}")
        return jsonify({"error": "Database error while creating registration."}), 500

    sync_to_sheet(registration_id, registration_data)

    # 7. Branching Logic (Pay Later vs Stripe Gateway)
    if data.get('payLater') or final_total == 0:
        
        if final_total == 0:
            logger.info(f"Free registration complete for {registration_id}")
            return jsonify({
                "url": f"{BASE_URL}/api/payment-success?reg_id={registration_id}", 
                "registrationId": registration_id
            })
        
        events_str = ", ".join([e['name'] for e in events])
        partners_str = ", ".join([f"{k}: {v}" for k, v in doubles_partners.items()])
        
        email_body = generate_receipt_email(
            first_name=player_details['firstName'], 
            reg_id=registration_id, 
            events_str=events_str, 
            partners_str=partners_str, 
            final_total=final_total, 
            status="Pending", 
            late_fee=late_fee
        )
        
        send_email(
            to_email=player_details['email'], 
            subject="Tournament Registration (Pending Payment)", 
            body=email_body
        )
        
        admin_body = f"<p>New PAY LATER Registration:<br>Player: {player_details['firstName']} {player_details['lastName']}<br>Ref ID: {registration_id}<br>Total Due: ${final_total}<br>Events: {events_str}</p>"
        send_email(
            to_email=ADMIN_EMAIL, 
            subject="New Tournament Registration (Pay Later)", 
            body=admin_body
        )
        
        return jsonify({
            "url": f"{BASE_URL}/success.html?reg_id={registration_id}", 
            "registrationId": registration_id
        })

    # Execute Stripe Checkout Flow
    try:
        logger.info(f"Generating Stripe session for {registration_id}. Processing Amount: {final_total}")
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'aud',
                    'unit_amount': int(round(final_total * 100)),
                    'product_data': {
                        'name': '2026 Gold Coast Open Registration'
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{BASE_URL}/api/payment-success?session_id={{CHECKOUT_SESSION_ID}}&reg_id={registration_id}",
            cancel_url=f"{BASE_URL}/registration?canceled=true",
        )
        return jsonify({
            "url": checkout_session.url, 
            "registrationId": registration_id
        })
        
    except stripe.error.StripeError as s_err:
        logger.error(f"Stripe API Error during session generation: {s_err}")
        return jsonify({"error": "Payment gateway is currently unavailable."}), 502
    except Exception as e:
        logger.error(f"Unexpected Stripe Error: {traceback.format_exc()}")
        return jsonify({"error": "Internal server error connecting to payment gateway."}), 500

@app.route('/api/payment-success', methods=['GET'])
def payment_success():
    """
    Webhook/Callback endpoint hit after a successful Stripe checkout payment.
    Reconciles the database balance, fires emails, and manages codes.
    """
    reg_id = request.args.get('reg_id')
    session_id = request.args.get('session_id', 'N/A')
    
    if not reg_id:
        return redirect(f"{BASE_URL}/")
        
    logger.info(f"Processing payment success callback webhook for Reg ID: {reg_id}")
    
    paid_at = get_local_now_str()
    doc_ref = db.collection('registrations').document(reg_id)
    doc = doc_ref.get()
    
    if doc.exists:
        record = doc.to_dict()
        history = record.get('history', [])
        late_fee = float(record.get('lateFee', 0.0))
        
        if history and len(history) > 0:
            history[0]['paymentStatus'] = 'Paid'
            history[0]['stripeSessionId'] = session_id
            history[0]['paidAt'] = paid_at

        try:
            doc_ref.update({
                "paymentStatus": "Paid",
                "paidAt": paid_at,
                "balanceDue": 0,
                "pendingReason": "N/A",
                "history": history
            })
            logger.info(f"Firestore record {reg_id} balance reconciled and marked as Paid.")
        except Exception as e:
            logger.error(f"Failed to update Firestore on payment success logic: {e}")
        
        updated_doc = doc_ref.get().to_dict()
        sync_to_sheet(reg_id, updated_doc)
        
        # Expire one-time discount codes if they were utilized in this session
        applied_code = updated_doc.get('discountCode')
        if applied_code:
            code_docs = list(db.collection('discount_codes').where(filter=FieldFilter('code', '==', applied_code)).stream())
            if code_docs:
                doc_data = code_docs[0].to_dict()
                if not doc_data.get('isPermanent', False):
                    db.collection('discount_codes').document(code_docs[0].id).update({"used": True})
                    logger.info(f"Single-use discount code {applied_code} effectively marked as consumed.")
        
        events_str = ", ".join([e['name'] for e in updated_doc.get('events', [])])
        partners_str = ", ".join([f"{k}: {v}" for k, v in updated_doc.get('doublesPartners', {}).items()])
        
        email_body = generate_receipt_email(
            first_name=updated_doc['player']['firstName'], 
            reg_id=reg_id, 
            events_str=events_str, 
            partners_str=partners_str, 
            final_total=updated_doc['finalTotal'], 
            status="Paid", 
            late_fee=late_fee
        )
        
        send_email(
            to_email=updated_doc['player']['email'], 
            subject="Tournament Registration Confirmation", 
            body=email_body
        )
        
        admin_body = f"<p>New Paid Registration:<br>Player: {updated_doc['player']['firstName']} {updated_doc['player']['lastName']}<br>Ref ID: {reg_id}<br>Total: ${updated_doc['finalTotal']}<br>Events: {events_str}<br>Partners: {partners_str}</p>"
        
        send_email(
            to_email=ADMIN_EMAIL, 
            subject="New Tournament Registration", 
            body=admin_body
        )
    else:
        logger.warning(f"CRITICAL: Payment success hit for non-existent Reg ID: {reg_id}")

    return redirect(f"/success.html?reg_id={reg_id}")


# ==============================================================================
# 11. UPDATE / BALANCE CHECKOUT API
# ==============================================================================
@app.route('/api/registration/lookup', methods=['POST'])
def lookup_reg():
    """Allows players to retrieve their registration details via email & National ID."""
    if not request.is_json:
        return jsonify({"error": "Invalid request format."}), 400
        
    data = request.json
    email_input = data.get('email', '').strip().lower()
    nat_id_input = data.get('nationalId', '').strip()
    
    if not email_input or not nat_id_input:
        return jsonify({"error": "Email and National ID are required."}), 400
        
    logger.info(f"Player portal lookup request: {email_input} / {nat_id_input}")
    
    try:
        docs = db.collection('registrations').where(filter=FieldFilter('player.nationalId', '==', nat_id_input)).stream()
        registrations = []
        
        for doc in docs:
            doc_dict = doc.to_dict()
            doc_email = doc_dict.get('player', {}).get('email', '').strip().lower()
            if doc_email == email_input:
                registrations.append(doc_dict | {"id": doc.id})
                
        if not registrations:
            logger.info("Lookup failed: Mismatch or not found.")
            return jsonify({"error": "No registration found with this Email and TTA Member Number."}), 404
            
        return jsonify(registrations[0])
        
    except Exception as e:
        logger.error(f"Lookup exception during DB read: {e}")
        return jsonify({"error": "Server error processing lookup."}), 500

@app.route('/api/registration/update-checkout', methods=['POST'])
def update_checkout():
    """Generates a Stripe session to charge the difference for newly added events."""
    data = request.json
    reg_id = data.get('reg_id')
    new_events = data.get('events', [])
    doubles_partners = data.get('doublesPartners', {})
    
    if not reg_id:
        return jsonify({"error": "Missing Registration ID."}), 400
        
    logger.info(f"Processing event update checkout session for {reg_id}")
    
    doc_ref = db.collection('registrations').document(reg_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        return jsonify({"error": "Registration not found."}), 404
        
    record = doc.to_dict()
    
    old_final_total = float(record.get('finalTotal', 0))
    try:
        base_total = sum(float(event.get('price', 0)) for event in new_events)
    except ValueError:
        return jsonify({"error": "Data formatting error in event pricing."}), 400
        
    ttq_levy = 5.00
    late_fee = float(record.get('lateFee', 0.0))
    discount_amount = float(record.get('discountAmount', 0))
    
    new_final_total = round(max(0.0, (base_total + ttq_levy + late_fee) - discount_amount), 2)
    difference = round(new_final_total - old_final_total, 2)
    
    if difference <= 0:
        logger.info("Update rejected: Proposed total is lower/equal to original. Disallowing refund hack.")
        return jsonify({
            "error": "Your new total is less than or equal to what you already paid. For refunds, please contact administration directly."
        }), 400
        
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'aud',
                    'unit_amount': int(round(difference * 100)),
                    'product_data': {
                        'name': '2026 Gold Coast Open - Registration Update'
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            metadata={
                'reg_id': reg_id, 
                'update_type': 'events_update'
            },
            success_url=f"{BASE_URL}/api/update-success?session_id={{CHECKOUT_SESSION_ID}}&reg_id={reg_id}",
            cancel_url=f"{BASE_URL}/update.html",
        )
        
        old_event_names = [e['name'] for e in record.get('events', [])]
        new_event_names = [e['name'] for e in new_events]
        added_events = [e for e in new_event_names if e not in old_event_names]
        removed_events = [e for e in old_event_names if e not in new_event_names]

        # Save pending state in DB so the webhook knows what to apply after the charge
        doc_ref.update({
            "pendingUpdate": {
                "events": new_events,
                "doublesPartners": doubles_partners,
                "newFinalTotal": new_final_total,
                "difference": difference,
                "addedEvents": added_events,
                "removedEvents": removed_events
            },
            "pendingReason": "Unpaid Event Update"
        })
        
        return jsonify({"url": checkout_session.url})
        
    except stripe.error.StripeError as s_err:
        logger.error(f"Stripe update error connection: {s_err}")
        return jsonify({"error": "Stripe gateway error."}), 502
    except Exception as e:
        logger.error(f"Update checkout error fatal: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/registration/pay-balance', methods=['POST'])
def pay_balance():
    """Generates a Stripe session specifically for paying off an existing debt balance."""
    data = request.json
    reg_id = data.get('reg_id')
    
    if not reg_id: 
        return jsonify({"error": "Missing Reg ID"}), 400
    
    doc_ref = db.collection('registrations').document(reg_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        return jsonify({"error": "Registration not found."}), 404
        
    record = doc.to_dict()
    balance = float(record.get('balanceDue', 0))
    
    if balance <= 0:
        return jsonify({"error": "You currently have no outstanding balance to pay."}), 400
        
    logger.info(f"Generating balance payment session for {reg_id}. Total Amount: {balance}")
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'aud',
                    'unit_amount': int(round(balance * 100)),
                    'product_data': {
                        'name': '2026 Gold Coast Open - Outstanding Balance'
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            metadata={
                'reg_id': reg_id, 
                'update_type': 'balance_payment'
            },
            success_url=f"{BASE_URL}/api/update-success?session_id={{CHECKOUT_SESSION_ID}}&reg_id={reg_id}",
            cancel_url=f"{BASE_URL}/update.html",
        )
        return jsonify({"url": checkout_session.url})
        
    except Exception as e:
        logger.error(f"Pay balance Stripe initialization error: {e}")
        return jsonify({"error": "Internal server error contacting Stripe."}), 500

@app.route('/api/update-success', methods=['GET'])
def update_success():
    """Handles routing logic post-payment for either an Event Update or a Balance Payment."""
    reg_id = request.args.get('reg_id')
    session_id = request.args.get('session_id', 'N/A')
    
    if not reg_id:
        return redirect("/")
        
    logger.info(f"Processing update success callback for Reg ID: {reg_id}")
    
    doc_ref = db.collection('registrations').document(reg_id)
    doc = doc_ref.get()
    
    if doc.exists:
        record = doc.to_dict()
        paid_at = get_local_now_str()
        history = record.get('history', [])
        late_fee = float(record.get('lateFee', 0.0))
        update_num = len(history)
        
        # Scenario A: User paid for an event addition
        if 'pendingUpdate' in record:
            logger.info("Executing Pending Update modification application.")
            
            update_data = record['pendingUpdate']
            new_final = update_data['newFinalTotal']
            new_events = update_data['events']
            new_partners = update_data['doublesPartners']
            diff = update_data['difference']
            
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
            
            rc_rating = record.get('player', {}).get('rcRating', 'N/A')
            warnings = evaluate_eligibility_warnings(rc_rating, new_events)
            
            doc_ref.update({
                "events": new_events,
                "doublesPartners": new_partners,
                "finalTotal": new_final,
                "paymentStatus": "Paid",
                "paidAt": paid_at,
                "balanceDue": 0,
                "pendingReason": "N/A",
                "eligibilityWarnings": warnings,
                "history": history,
                "pendingUpdate": firestore.DELETE_FIELD
            })
            
            updated_record = doc_ref.get().to_dict()
            sync_to_sheet(reg_id, updated_record)
                
            events_str = ", ".join([e['name'] for e in new_events])
            partners_str = ", ".join([f"{k}: {v}" for k, v in new_partners.items()])
            
            email_body = generate_receipt_email(
                first_name=record['player']['firstName'], 
                reg_id=reg_id, 
                events_str=events_str, 
                partners_str=partners_str, 
                final_total=new_final, 
                status="Paid", 
                late_fee=late_fee
            )
            send_email(
                to_email=record['player']['email'], 
                subject="Registration Update Confirmed", 
                body=email_body
            )
            
        # Scenario B: User paid off a standing Pay On Day balance
        elif float(record.get('balanceDue', 0)) > 0:
            logger.info("Executing Balance Repayment application in database.")
            
            old_total = float(record.get('finalTotal', 0))
            balance = float(record.get('balanceDue', 0))
            
            history.append({
                "updateNumber": update_num,
                "type": f"Update #{update_num} (Balance Payment)",
                "timestamp": paid_at,
                "amountPaid": balance,
                "previousTotal": old_total,
                "newTotal": old_total,
                "paymentStatus": "Paid",
                "stripeSessionId": session_id
            })
            
            doc_ref.update({
                "paymentStatus": "Paid",
                "paidAt": paid_at,
                "balanceDue": 0,
                "pendingReason": "N/A",
                "history": history
            })
            
            updated_record = doc_ref.get().to_dict()
            sync_to_sheet(reg_id, updated_record)

    return redirect(f"/success.html?reg_id={reg_id}&updated=true")


# ==============================================================================
# 12. AI-POWERED ZERMELO SYNC ENGINE
# ==============================================================================
@app.route('/api/admin/sync-zermelo', methods=['POST'])
def admin_sync_zermelo():
    """
    Scrapes ALL event files from Zermelo FTP via Playwright (Bypassing InfinityFree).
    Uses Gemini 3.1 Pro to convert raw HTML tables into clean JSON objects natively.
    Falls back to a rigorous manual parser if Gemini is unavailable.
    """
    logger.info("Initiating comprehensive Zermelo synchronization process.")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = browser.new_context(user_agent=SCRAPER_HEADERS["User-Agent"])
            page = context.new_page()
            
            logger.debug(f"Navigating to FTP: {ZERMELO_HOST_URL}/Tournament.htm")
            page.goto(f"{ZERMELO_HOST_URL}/Tournament.htm")
            page.wait_for_timeout(3500) 
            
            soup = BeautifulSoup(page.content(), 'html.parser')
            links = []
            
            # Case-insensitive link scraper to find ALL event pages
            for a in soup.find_all('a', href=True):
                href = a['href'].strip()
                href_lower = href.lower()
                if (href_lower.endswith('.htm') or href_lower.endswith('.html')) and 'tournament.htm' not in href_lower:
                    event_title = a.get_text(strip=True) or href
                    links.append((event_title, href))

            if not links:
                browser.close()
                logger.error("No event files found on Zermelo FTP server.")
                return jsonify({"error": "No event files found on Zermelo FTP server."}), 404

            logger.info(f"Found {len(links)} Zermelo event files. Processing integration...")
            batch = db.batch()
            draws_ref = db.collection('draws')
            count = 0

            # Initialize Gemini SDK client if available
            genai_client = genai.Client(api_key=GEMINI_API_KEY) if (GEMINI_AVAILABLE and GEMINI_API_KEY) else None

            for name, href in links:
                logger.debug(f"Fetching {name} from /{href}")
                page.goto(f"{ZERMELO_HOST_URL}/{href}")
                page.wait_for_timeout(1000) 
                
                ev_soup = BeautifulSoup(page.content(), 'html.parser')
                html_snippet = ev_soup.body.decode_contents() if ev_soup.body else str(ev_soup)
                
                parsed_dict = None

                # Attempt AI Extraction First
                if genai_client:
                    try:
                        logger.info(f"Delegating {name} parsing to Gemini 3.1 Pro API.")
                        prompt = (
                            f"Analyze this table tennis tournament HTML page for the event '{name}'. "
                            f"Extract all groups, players, win/loss stats, and knockout elimination matches. "
                            f"HTML:\n\n{html_snippet}"
                        )
                        response = genai_client.models.generate_content(
                            model='gemini-3.1-pro',
                            contents=prompt,
                            config={
                                'response_mime_type': 'application/json',
                                'response_schema': EventDraw,
                                'temperature': 0.1 # Low variance
                            },
                        )
                        
                        if response.parsed:
                            parsed_dict = response.parsed.dict()
                            logger.info(f"Gemini extraction successful for {name}")
                            
                    except Exception as ai_err:
                        logger.warning(f"Gemini parsing failed for {name}: {ai_err}")

                # Fallback to pure manual parser if AI fails or isn't configured
                if not parsed_dict:
                    logger.info(f"Using manual BeautifulSoup fallback parser for {name}.")
                    parsed_dict = ZermeloManualParser.parse_event_html(name, html_snippet)

                # Ensure minimum viability
                if not parsed_dict.get("eventName"):
                    parsed_dict["eventName"] = name

                # Map event to strict catalog ID to preserve relationship integrity
                mapped_id = hashlib.md5(name.encode()).hexdigest()[:8]
                for ev_id, ev_title in EVENT_CATALOG.items():
                    if name.lower() in ev_title.lower() or ev_title.lower() in name.lower():
                        mapped_id = str(ev_id)
                        break

                parsed_dict["id"] = mapped_id
                parsed_dict["name"] = name 
                parsed_dict["updatedAt"] = firestore.SERVER_TIMESTAMP
                
                doc_ref = draws_ref.document(mapped_id)
                batch.set(doc_ref, parsed_dict)
                count += 1

            batch.commit()
            browser.close()
            logger.info(f"Successfully synced {count} events to Firestore cache.")
            return jsonify({"status": "success", "count": count})
            
    except Exception as e:
        logger.error(f"Zermelo Sync Exception Fatal: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/public/draws', methods=['GET'])
def get_public_draws():
    """Retrieves all parsed event JSON arrays for native rendering on the frontend."""
    try:
        docs = db.collection('draws').stream()
        draws = []
        for d in docs:
            data = d.to_dict()
            data["id"] = d.id
            draws.append(data)
        
        # Sort dynamically by event number if available
        def extract_event_num(name):
            match = re.search(r'#(\d+)', name)
            return int(match.group(1)) if match else 999
            
        draws.sort(key=lambda x: extract_event_num(x.get('eventName', x.get('name', ''))))
        
        return jsonify({"status": "success", "draws": draws})
    except Exception as e:
        logger.error(f"Error fetching public draws: {e}")
        return jsonify({"error": "Internal server error fetching draws"}), 500

# ==============================================================================
# 13. MATCH CONTROLLER & LIVE TABLES APP
# ==============================================================================
def scrape_zermelo_matches():
    """DISABLED: InfinityFree IP ban triggered. Bypassing scraper to keep server alive."""
    return []

@app.route('/api/admin/active-matches', methods=['GET'])
def get_active_matches():
    """Endpoint for Admin Panel to load all matches and active table numbers."""
    try:
        scraped_matches = scrape_zermelo_matches()
        assignments_ref = db.collection('table_assignments').stream()
        assigned_dict = {doc.id: doc.to_dict().get('table', 'Unassigned') for doc in assignments_ref}
        
        for match in scraped_matches:
            match['table'] = assigned_dict.get(match['id'], 'Unassigned')
            
        return jsonify({"status": "success", "matches": scraped_matches})
    except Exception as e:
        logger.error(f"Error serving active matches: {e}")
        return jsonify({"error": "Failed to fetch matches"}), 500

@app.route('/api/admin/assign-table', methods=['POST'])
def assign_table():
    """Allows Admins to overwrite the physical table number for a live match."""
    data = request.json
    match_id = data.get('matchId')
    table_num = data.get('tableNumber')
    
    if not match_id or not table_num: 
        return jsonify({"error": "Missing match ID or table data."}), 400
        
    try:
        db.collection('table_assignments').document(match_id).set({ 
            "table": table_num, 
            "updatedAt": firestore.SERVER_TIMESTAMP 
        }, merge=True)
        logger.info(f"Assigned Match {match_id} to Table {table_num}")
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Table Assignment Error: {e}")
        return jsonify({"error": "Database error writing table status"}), 500


# ==============================================================================
# 14. PLAYER SCHEDULE LOOKUP (COMPREHENSIVE)
# ==============================================================================
@app.route('/api/schedule/lookup', methods=['POST'])
def lookup_schedule():
    """Returns a specific player's upcoming matches and assigned tables."""
    try:
        data = request.json
        first = data.get('firstName', '').strip().lower()
        last = data.get('lastName', '').strip().lower()
        dob = data.get('dob', '').strip()

        if not first or not last or not dob:
            return jsonify({"error": "Please provide First Name, Last Name, and Date of Birth."}), 400

        logger.info(f"Schedule lookup execution for: {first} {last}")
        
        docs = db.collection('registrations').stream()
        player_found = False
        player_data = {}
        registered_events = []
        
        for doc in docs:
            d = doc.to_dict()
            p = d.get('player', {})
            db_first = p.get('firstName', '').strip().lower()
            db_last = p.get('lastName', '').strip().lower()
            db_dob = p.get('dob', '').strip()
            
            if db_first == first and db_last == last and db_dob == dob:
                player_found = True
                player_data = {"firstName": p.get('firstName', ''), "lastName": p.get('lastName', '')}
                registered_events = d.get('events', [])
                break

        if not player_found:
            return jsonify({"error": "No registration found matching those details."}), 404

        active_matches = scrape_zermelo_matches()
        assignments_ref = db.collection('table_assignments').stream()
        assigned_dict = {doc.id: doc.to_dict().get('table', 'Unassigned') for doc in assignments_ref}

        my_matches = []
        last_name_check = player_data.get('lastName', '').lower()
        
        for match in active_matches:
            m_p1 = match['p1'].lower()
            m_p2 = match['p2'].lower()
            
            if last_name_check in m_p1 or last_name_check in m_p2:
                opponent = match['p2'] if last_name_check in m_p1 else match['p1']
                table = assigned_dict.get(match['id'], 'Unassigned')
                my_matches.append({
                    "event": match['event'], 
                    "opponent": opponent, 
                    "table": table
                })

        if len(my_matches) == 0 and len(registered_events) > 0:
            for ev in registered_events:
                ev_name = ev.get('name', 'Unknown Event') if isinstance(ev, dict) else str(ev)
                my_matches.append({
                    "event": ev_name, 
                    "opponent": "TBD (Draw Pending)", 
                    "table": "Unassigned"
                })

        return jsonify({
            "status": "success", 
            "player": player_data, 
            "events": registered_events, 
            "currentMatches": my_matches
        })
        
    except Exception as e:
        logger.error(f"Schedule endpoint failed fatally: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# 15. ADMIN DASHBOARD STATS
# ==============================================================================
@app.route('/api/admin/stats', methods=['GET'])
def get_admin_stats():
    """Computes global tournament financial stats from all registration records."""
    try:
        docs = db.collection('registrations').stream()
        total_value = 0
        collected = 0
        outstanding = 0
        players = 0
        pending = 0
        
        for doc in docs:
            d = doc.to_dict()
            players += 1
            f_total = float(d.get('finalTotal', 0))
            b_due = float(d.get('balanceDue', 0))
            
            total_value += f_total
            outstanding += b_due
            collected += (f_total - b_due)
            
            if b_due > 0 or 'Pending' in d.get('paymentStatus', ''): 
                pending += 1

        settings_doc = db.collection('settings').document('financials').get()
        if settings_doc.exists:
            override_val = settings_doc.to_dict().get('collectedOverride')
            if override_val is not None:
                collected = float(override_val)
                total_value = collected + outstanding
                
        return jsonify({
            "totalValue": total_value, 
            "collectedRevenue": collected, 
            "outstandingBalance": outstanding, 
            "totalPlayers": players, 
            "pendingPayments": pending
        })
    except Exception as e:
        logger.error(f"Admin Stats calculation failed: {e}")
        return jsonify({"error": "Failed to calculate stats"}), 500

@app.route('/api/admin/override-revenue', methods=['POST'])
def override_revenue():
    """Allows admins to hard-override the revenue collected total (bypass calculation)."""
    data = request.json
    if data.get('code') != '228415': 
        logger.warning("Failed admin override due to bad passcode.")
        return jsonify({"error": "Invalid passcode."}), 403
        
    val = data.get('value')
    try:
        if val is None or str(val).strip() == "": 
            db.collection('settings').document('financials').set({"collectedOverride": None}, merge=True)
            logger.info("Cleared revenue override.")
        else:
            db.collection('settings').document('financials').set({"collectedOverride": float(val)}, merge=True)
            logger.info(f"Set revenue override to: {val}")
        return jsonify({"status": "success"})
    except ValueError: 
        return jsonify({"error": "Invalid number format."}), 400
    except Exception as e:
        logger.error(f"Override logic failed: {e}")
        return jsonify({"error": "Internal DB error."}), 500


# ==============================================================================
# 16. ADMIN REGISTRATION MANAGEMENT
# ==============================================================================
@app.route('/api/admin/registrations', methods=['GET'])
def get_registrations():
    """Pulls all raw registration documents."""
    try:
        registrations = []
        docs = db.collection('registrations').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            registrations.append(data)
        return jsonify(registrations)
    except Exception as e:
        logger.error(f"Retrieval of registrations failed: {e}")
        return jsonify({"error": "Failed to pull records"}), 500

@app.route('/api/admin/event-entries', methods=['GET'])
def get_event_entries():
    """Reconstructs player dictionaries nested inside Event groupings."""
    try:
        docs = db.collection('registrations').stream()
        events_map = {}
        for doc in docs:
            d = doc.to_dict()
            player = d.get('player', {})
            first_name = player.get('firstName', '').strip()
            last_name = player.get('lastName', '').strip()
            player_name = f"{first_name} {last_name}".strip()
            
            events = d.get('events', [])
            for ev in events:
                ev_name = ev.get('name', 'Unknown Event')
                if ev_name not in events_map: 
                    events_map[ev_name] = { 
                        "eventId": ev.get('id', 0), 
                        "eventName": ev_name, 
                        "players": [] 
                    }
                    
                events_map[ev_name]["players"].append({
                    "regId": doc.id, 
                    "playerName": player_name, 
                    "email": player.get('email', 'N/A'),
                    "phone": player.get('phone', 'N/A'), 
                    "rcRating": player.get('rcRating', 'N/A'),
                    "club": player.get('club', 'N/A'), 
                    "paymentStatus": d.get('paymentStatus', 'Pending')
                })
                
        event_list = list(events_map.values())
        event_list.sort(key=lambda x: x['eventName'])
        return jsonify({"status": "success", "events": event_list})
        
    except Exception as e: 
        logger.error(f"Event Entries rebuild failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/manual-register', methods=['POST'])
def manual_register():
    """Direct backdoor creation of a player registration by an admin, bypassing Stripe."""
    data = request.json
    rc_val = data.get('rcId', 'N/A')
    never_played = data.get('neverPlayed', False)
    
    if never_played: 
        rc_val = "Never Played"
        
    rc_rating = data.get('rcRating', 'N/A') 

    # Attempt lookup if valid TTA ID provided
    if not never_played and data.get('nationalId') and data.get('nationalId') != 'N/A':
        found_rc, found_rating = lookup_rc_by_tta_id(data.get('nationalId'))
        if found_rc != "N/A":
            rc_val = found_rc
            rc_rating = found_rating

    registered_at = get_local_now_str()
    paid_at = registered_at if data.get('status') == 'Paid' else 'N/A'
    
    try:
        total_val = float(data.get('totalPaid', 0))
    except ValueError:
        return jsonify({"error": "Bad amount"}), 400
        
    pending_reason = "N/A" if data.get('status') == 'Paid' else "Manual Entry (Unpaid)"

    events = data.get('events', [])
    warnings = evaluate_eligibility_warnings(rc_rating, events)

    initial_history = {
        "updateNumber": 0, 
        "type": "Admin Manual Entry", 
        "timestamp": registered_at,
        "amountCharged": total_val, 
        "paymentStatus": data.get('status', 'Paid'),
        "events": [e['name'] for e in events], 
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
        "events": events, 
        "doublesPartners": {}, 
        "baseTotal": total_val, 
        "ttqLevy": 0,
        "discountCode": "MANUAL", 
        "discountAmount": 0, 
        "lateFee": 0.0, 
        "originalTotal": total_val,
        "finalTotal": total_val, 
        "balanceDue": 0 if data.get('status') == 'Paid' else total_val,
        "paymentStatus": data.get('status', 'Paid'), 
        "pendingReason": pending_reason,
        "eligibilityWarnings": warnings, 
        "registeredAt": registered_at, 
        "paidAt": paid_at,
        "history": [initial_history], 
        "timestamp": firestore.SERVER_TIMESTAMP
    }
    
    try:
        doc_ref = db.collection('registrations').document()
        doc_ref.set(registration_data)
        logger.info(f"Manual registration created for {data.get('firstName')} {data.get('lastName')} -> {doc_ref.id}")
        sync_to_sheet(doc_ref.id, registration_data)
        return jsonify({"status": "success", "id": doc_ref.id})
    except Exception as e:
        logger.error(f"Manual reg commit failed: {e}")
        return jsonify({"error": "Database error"}), 500

@app.route('/api/admin/registrations/<reg_id>', methods=['PUT'])
def update_registration(reg_id):
    """Full overwrite PUT command from Admin Edit Modal."""
    if not request.is_json:
        return jsonify({"error": "Bad JSON payload"}), 400
        
    data = request.json
    doc_ref = db.collection('registrations').document(reg_id)
    doc = doc_ref.get()
    
    if not doc.exists: 
        return jsonify({"error": "Registration not found"}), 404
        
    record = doc.to_dict()
    history = record.get('history', [])
    now_str = get_local_now_str()

    update_payload = {}
    current_player = record.get('player', {})
    
    if 'player' in data:
        for k, v in data['player'].items(): 
            current_player[k] = v
            update_payload[f'player.{k}'] = v
            
    current_events = record.get('events', [])
    if 'events' in data: 
        current_events = data['events']
        update_payload['events'] = current_events
        
    rc_rating = current_player.get('rcRating', 'N/A')
    warnings = evaluate_eligibility_warnings(rc_rating, current_events)
    update_payload['eligibilityWarnings'] = warnings
        
    if 'doublesPartners' in data: 
        update_payload['doublesPartners'] = data['doublesPartners']
    if 'lateFee' in data: 
        update_payload['lateFee'] = float(data['lateFee'])
    if 'balanceDue' in data: 
        update_payload['balanceDue'] = float(data['balanceDue'])
    if 'finalTotal' in data: 
        update_payload['finalTotal'] = float(data['finalTotal'])
    if 'manualFeeWaived' in data: 
        update_payload['manualFeeWaived'] = data['manualFeeWaived']
        
    if 'paymentStatus' in data: 
        update_payload['paymentStatus'] = data['paymentStatus']
        
        if 'Paid' in data['paymentStatus']:
            update_payload['paidAt'] = now_str
            update_payload['balanceDue'] = 0
            update_payload['pendingReason'] = 'N/A'
            
        elif 'Pending' in data['paymentStatus']:
            update_payload['balanceDue'] = data.get('balanceDue', data.get('finalTotal', record.get('finalTotal', 0)))
            update_payload['pendingReason'] = 'Admin Overwrite (Unpaid)'

    if 'events' in data or 'paymentStatus' in data:
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

    try:
        doc_ref.update(update_payload)
        logger.info(f"Successfully processed full admin overwrite for {reg_id}")
        updated_record = doc_ref.get().to_dict()
        sync_to_sheet(reg_id, updated_record)
        return jsonify({"status": "updated"})
    except Exception as e:
        logger.error(f"Overwrite failed: {e}")
        return jsonify({"error": "Failed to update record"}), 500

@app.route('/api/admin/registrations/<reg_id>', methods=['DELETE'])
def delete_registration(reg_id):
    """Hard deletes a player from DB and attempts deletion from Sheet."""
    try:
        db.collection('registrations').document(reg_id).delete()
        logger.warning(f"CRITICAL: Record {reg_id} deleted permanently.")
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        return jsonify({"error": "Could not delete document."}), 500
        
    try:
        cell = sheet.find(reg_id)
        if cell: 
            sheet.delete_row(cell.row)
            logger.info(f"Row removed from Google Sheets for {reg_id}.")
    except Exception as gs_err: 
        logger.error(f"Could not remove from Sheet: {gs_err}")
        
    return jsonify({"status": "deleted"})


# ==============================================================================
# 17. PROMOTIONAL DISCOUNT API
# ==============================================================================
@app.route('/api/admin/discount-codes', methods=['GET', 'POST'])
def handle_discount_codes():
    """Generates random code chunks or retrieves all codes for Admin."""
    if request.method == 'POST':
        data = request.json
        amount = float(data.get('amount', 5.0))
        discount_type = data.get('discountType', 'dollar')
        is_perm = data.get('isPermanent', False)
        
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        try:
            db.collection('discount_codes').add({ 
                "code": code, 
                "discountAmount": amount, 
                "discountType": discount_type, 
                "used": False, 
                "isPermanent": is_perm, 
                "timestamp": firestore.SERVER_TIMESTAMP 
            })
            logger.info(f"New discount code created: {code}")
            return jsonify({
                "code": code, 
                "amount": amount, 
                "discountType": discount_type, 
                "isPermanent": is_perm
            })
        except Exception as e:
            logger.error(f"Failed to create code: {e}")
            return jsonify({"error": "DB failure"}), 500
            
    else:
        try:
            codes = []
            docs = db.collection('discount_codes').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
            for doc in docs:
                d = doc.to_dict()
                d['id'] = doc.id
                codes.append(d)
            return jsonify(codes)
        except Exception as e:
            logger.error(f"Failed to fetch codes: {e}")
            return jsonify({"error": "Failed fetching codes"}), 500

@app.route('/api/admin/discount-codes/<doc_id>', methods=['PUT'])
def update_discount_code(doc_id):
    """Sets a code's status (Used / Expired)."""
    data = request.json
    try:
        db.collection('discount_codes').document(doc_id).update(data)
        logger.info(f"Discount code {doc_id} updated.")
        return jsonify({"status": "updated"})
    except Exception as e:
        logger.error(f"Discount update failed: {e}")
        return jsonify({"error": "Failed to update code"}), 500


# ==============================================================================
# 18. ADMIN DATA SYNC TOOLS
# ==============================================================================
@app.route('/api/admin/export-zermelo-players', methods=['GET'])
def export_zermelo_players():
    """Generates the specific CSV data blob for Zermelo import."""
    try:
        docs = db.collection('registrations').where(filter=FieldFilter('zermeloExported', '!=', True)).stream()
        players_data = []
        doc_ids_to_update = []
        
        for doc in docs:
            d = doc.to_dict()
            p = d.get('player', {})
            rc_id = p.get('rcId', '').strip()
            never_played = p.get('neverPlayed', False)
            
            # Zermelo export mandates an RC rating structure
            if never_played or rc_id.lower() in ["", "n/a", "never played", "none"]: 
                continue
                
            events = d.get('events', [])
            event_ids = [str(e.get('id')) for e in events if 'id' in e and e.get('id') not in DOUBLES_EVENT_IDS]
            events_str = " ".join(event_ids)
            
            last_name = p.get('lastName', '').strip()
            first_name = p.get('firstName', '').strip()
            full_name = f"{first_name} {last_name}".strip()
            
            players_data.append({ 
                "Name": full_name, 
                "Ratings Central ID": rc_id, 
                "Events": events_str, 
                "Look up Ratings": "RC", 
                "Look Up Personal Info": "RC", 
                "Check In": "Here Now", 
                "Draw Club": "", 
                "Use Club For Draw Club": "Y" 
            })
            doc_ids_to_update.append(doc.id)
            
        logger.info(f"Exported {len(players_data)} rated players to Zermelo payload.")
        return jsonify({ "players": players_data, "docIds": doc_ids_to_update })
    except Exception as e:
        logger.error(f"Zermelo Export build failed: {e}")
        return jsonify({"error": "Failed building export"}), 500

@app.route('/api/admin/mark-exported', methods=['POST'])
def mark_exported():
    """Tags exported players so they are ignored in future CSV generations."""
    data = request.json
    doc_ids = data.get('docIds', [])
    try:
        batch = db.batch()
        count = 0
        for doc_id in doc_ids:
            doc_ref = db.collection('registrations').document(doc_id)
            batch.update(doc_ref, {"zermeloExported": True})
            count += 1
        batch.commit()
        
        logger.info(f"Marked {count} documents as exported.")
        return jsonify({"status": "success", "updatedCount": count})
    except Exception as e:
        logger.error(f"Failed marking exports: {e}")
        return jsonify({"error": "Database error"}), 500

@app.route('/api/admin/push-to-zermelo-sheet', methods=['POST'])
def push_zermelo_sheet():
    """Wipes and rewrites the connected Zermelo-import Google Sheet."""
    if not zermelo_sheet:
        return jsonify({"error": "Zermelo sheet uninitialized"}), 500
        
    try:
        docs = db.collection('registrations').stream()
        rows_data = []
        headers = [
            "Name", 
            "Ratings Central ID", 
            "Events", 
            "Look up Ratings", 
            "Look Up Personal Info", 
            "Check In", 
            "Draw Club", 
            "Use Club For Draw Club"
        ]
        rows_data.append(headers)
        
        for doc in docs:
            d = doc.to_dict()
            p = d.get('player', {})
            rc_id = p.get('rcId', '').strip()
            never_played = p.get('neverPlayed', False)
            
            if never_played or rc_id.lower() in ["", "n/a", "never played", "none"]: 
                continue
                
            events = d.get('events', [])
            event_ids = [str(e.get('id')) for e in events if 'id' in e and e.get('id') not in DOUBLES_EVENT_IDS]
            events_str = " ".join(event_ids)
            
            last_name = p.get('lastName', '').strip()
            first_name = p.get('firstName', '').strip()
            full_name = f"{first_name} {last_name}".strip()
            
            row = [
                full_name, 
                rc_id, 
                events_str, 
                "RC", 
                "RC", 
                "Here Now", 
                "", 
                "Y"
            ]
            rows_data.append(row)
            
        zermelo_sheet.batch_clear(["A1:H1000"])
        
        if len(rows_data) > 1:
            cell_list = zermelo_sheet.range(f"A1:H{len(rows_data)}")
            flat_data = [item for sublist in rows_data for item in sublist]
            for i, val in enumerate(flat_data): 
                cell_list[i].value = val
            zermelo_sheet.update_cells(cell_list, value_input_option='USER_ENTERED')
            
        logger.info(f"Pushed {len(rows_data)-1} players to Zermelo live GSheet.")
        return jsonify({"status": "success", "count": len(rows_data)-1})
        
    except Exception as e: 
        logger.error(f"Zermelo Push Sheet Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/bulk-fix-rc', methods=['POST'])
def bulk_fix_rc():
    """Iterates all players, pings RC database strictly to fill gaps, then rebuilds Master Sheet."""
    try:
        docs = db.collection('registrations').stream()
        updated_count = 0
        
        for doc in docs:
            record = doc.to_dict()
            reg_id = doc.id
            p = record.get('player', {})
            events = record.get('events', [])
            
            tta_id = p.get('nationalId', '')
            never_played = p.get('neverPlayed', False)
            found_rc, found_rating = p.get('rcId', 'N/A'), p.get('rcRating', 'N/A')
            
            if not never_played and tta_id and tta_id != "N/A":
                fetched_rc, fetched_rating = lookup_rc_by_tta_id(tta_id)
                if fetched_rc == "N/A": 
                    fetched_rc, fetched_rating = find_missing_rc(
                        tta_id, 
                        p.get('firstName', ''), 
                        p.get('lastName', '')
                    )
                if fetched_rc != "N/A": 
                    found_rc, found_rating = fetched_rc, fetched_rating
                    
            warnings = evaluate_eligibility_warnings(found_rating, events)
            
            db.collection('registrations').document(reg_id).update({ 
                "player.rcId": found_rc, 
                "player.rcRating": found_rating, 
                "eligibilityWarnings": warnings 
            })
            updated_count += 1

        logger.info(f"Bulk RC update completed. Modifying Master Sheet with updated stats.")
        
        all_docs = db.collection('registrations').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        rows_data = []
        
        for doc in all_docs:
            rec = doc.to_dict()
            rid = doc.id
            pl = rec.get('player', {})
            events = rec.get('events', [])
            e_str = ", ".join([e['name'] for e in events])
            pt_str = ", ".join([f"{k}: {v}" for k, v in rec.get('doublesPartners', {}).items()])
            
            total_events = len(events)
            doubles_count = sum(1 for e in events if e.get('id') in DOUBLES_EVENT_IDS)
            singles_count = total_events - doubles_count
            
            warns = rec.get('eligibilityWarnings', [])
            warnings_str = " | ".join(warns) if warns else ""
            
            row = [
                rid, 
                pl.get('firstName',''), 
                pl.get('lastName',''), 
                pl.get('email',''), 
                pl.get('phone',''), 
                pl.get('dob','N/A'), 
                pl.get('gender','N/A'),
                pl.get('nationalId','N/A'), 
                pl.get('club','N/A'), 
                pl.get('rcId','N/A'), 
                pl.get('rcRating','N/A'), 
                str(pl.get('neverPlayed', False)).upper(),
                e_str, 
                pt_str, 
                rec.get('ttqLevy', 5.0), 
                rec.get('discountAmount', 0), 
                rec.get('finalTotal', 0), 
                rec.get('paymentStatus', 'Pending'),
                rec.get('registeredAt', 'N/A'), 
                rec.get('paidAt', 'N/A'), 
                singles_count, 
                doubles_count, 
                total_events, 
                warnings_str
            ]
            rows_data.append(row)
            
        if sheet:
            sheet.batch_clear(["A2:X1000"])
            if rows_data:
                cell_list = sheet.range(f"A2:X{len(rows_data)+1}")
                flat_data = [item for sublist in rows_data for item in sublist]
                for i, val in enumerate(flat_data): 
                    cell_list[i].value = val
                sheet.update_cells(cell_list, value_input_option='USER_ENTERED')
                
        return jsonify({
            "status": "success", 
            "updatedCount": updated_count, 
            "totalRows": len(rows_data)
        })
        
    except Exception as e:
        logger.error(f"Bulk RC update catastrophic failure: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/rebuild-sheet', methods=['POST'])
def rebuild_sheet():
    """Wipes and reconstructs the Google Sheet exactly to database state."""
    if not sheet:
        return jsonify({"error": "Master sheet uninitialized"}), 500
        
    try:
        all_docs = db.collection('registrations').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        rows_data = []
        for doc in all_docs:
            rec = doc.to_dict()
            rid = doc.id
            pl = rec.get('player', {})
            events = rec.get('events', [])
            e_str = ", ".join([e['name'] for e in events])
            pt_str = ", ".join([f"{k}: {v}" for k, v in rec.get('doublesPartners', {}).items()])
            
            total_events = len(events)
            doubles_count = sum(1 for e in events if e.get('id') in DOUBLES_EVENT_IDS)
            singles_count = total_events - doubles_count
            warns = rec.get('eligibilityWarnings', [])
            warnings_str = " | ".join(warns) if warns else ""
            
            row = [
                rid, 
                pl.get('firstName',''), 
                pl.get('lastName',''), 
                pl.get('email',''), 
                pl.get('phone',''), 
                pl.get('dob','N/A'), 
                pl.get('gender','N/A'),
                pl.get('nationalId','N/A'), 
                pl.get('club','N/A'), 
                pl.get('rcId','N/A'), 
                pl.get('rcRating','N/A'), 
                str(pl.get('neverPlayed', False)).upper(),
                e_str, 
                pt_str, 
                rec.get('ttqLevy', 5.0), 
                rec.get('discountAmount', 0), 
                rec.get('finalTotal', 0), 
                rec.get('paymentStatus', 'Pending'),
                rec.get('registeredAt', 'N/A'), 
                rec.get('paidAt', 'N/A'), 
                singles_count, 
                doubles_count, 
                total_events, 
                warnings_str
            ]
            rows_data.append(row)
            
        sheet.batch_clear(["A2:X1000"])
        
        if rows_data:
            cell_list = sheet.range(f"A2:X{len(rows_data)+1}")
            flat_data = [item for sublist in rows_data for item in sublist]
            for i, val in enumerate(flat_data): 
                cell_list[i].value = val
            sheet.update_cells(cell_list, value_input_option='USER_ENTERED')
            
        logger.info(f"Rebuild completed with {len(rows_data)} rows.")
        return jsonify({"status": "success", "rows": len(rows_data)})
        
    except Exception as e:
        logger.error(f"Rebuild error: {e}")
        return jsonify({"error": "Failed to rebuild."}), 500


@app.route('/api/admin/registrations/<reg_id>/resync', methods=['POST'])
def admin_resync(reg_id):
    """Force an individual RC refresh and row sync for a single player."""
    try:
        doc_ref = db.collection('registrations').document(reg_id)
        doc = doc_ref.get()
        if not doc.exists: 
            return jsonify({"error": "Registration not found"}), 404
            
        record = doc.to_dict()
        p = record.get('player', {})
        events = record.get('events', [])
        rc_val = p.get('rcId', '').strip()
        never_played = p.get('neverPlayed', False)
        
        if not never_played and (not rc_val or rc_val.lower() == 'n/a'):
            found_rc, found_rating = lookup_rc_by_tta_id(p.get('nationalId', ''))
            if found_rc == "N/A": 
                found_rc, found_rating = find_missing_rc(
                    p.get('nationalId', ''), 
                    p.get('firstName', ''), 
                    p.get('lastName', '')
                )
                
            if found_rc != "N/A":
                p['rcId'] = found_rc
                p['rcRating'] = found_rating
                warnings = evaluate_eligibility_warnings(found_rating, events)
                
                doc_ref.update({ 
                    "player.rcId": found_rc, 
                    "player.rcRating": found_rating, 
                    "eligibilityWarnings": warnings 
                })
                
                record['player']['rcId'] = found_rc
                record['player']['rcRating'] = found_rating
                record['eligibilityWarnings'] = warnings
                
        sync_to_sheet(reg_id, record)
        logger.info(f"Individual resync complete for {reg_id}")
        
        return jsonify({
            "status": "success", 
            "newRcId": p.get('rcId', rc_val)
        })
        
    except Exception as e:
        logger.error(f"Individual resync error: {e}")
        return jsonify({"error": "Internal error"}), 500

# ==============================================================================
# SERVER BOOT
# ==============================================================================
if __name__ == '__main__':
    logger.info("======================================================")
    logger.info("   GCTTA MASTER TOURNAMENT SERVER ONLINE (PORT 5000)  ")
    logger.info("======================================================")
    app.run(host='0.0.0.0', port=5000)