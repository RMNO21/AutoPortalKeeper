"""
====================================================================
AutoPortal Keeper - Universal Captive Portal Auto-Login & Rotation Service
Developed by: Raman Tondro
GitHub: https://github.com/RMNO21
License: MIT
====================================================================
"""

import base64
import ctypes
from ctypes import wintypes
import http.cookiejar
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "accounts.json")
STATE_FILE = os.path.join(BASE_DIR, "state.json")

# Connectivity check endpoints (ultra-low bandwidth HTTP 204)
CHECK_URL = "http://connectivitycheck.gstatic.com/generate_204"
BACKUP_CHECK_URL = "http://www.msftconnecttest.com/connecttest.txt"

CHECK_INTERVAL_ONLINE = 15     # Sleep interval when connected (seconds)
CHECK_INTERVAL_OFFLINE = 5     # Check interval when disconnected (seconds)
COOLDOWN_TIME = 30             # Cooldown for accounts reaching concurrent connection limit (seconds)

# Windows DPAPI security structures for in-memory decryption
class DATA_BLOB(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_byte))]

def decrypt_password(cipher_b64):
    """Decrypt passwords using native Windows DPAPI (tied to current user profile)"""
    if not cipher_b64:
        return ""
    try:
        raw_data = base64.b64decode(cipher_b64)
        blob_in = DATA_BLOB(len(raw_data), ctypes.cast(ctypes.create_string_buffer(raw_data), ctypes.POINTER(ctypes.c_byte)))
        blob_out = DATA_BLOB()
        if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
            buffer = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return buffer.decode('utf-8')
    except Exception:
        pass
    return cipher_b64

# SSL Context to tolerate internal/self-signed certificates common on institutional captive portals
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

cookie_jar = http.cookiejar.CookieJar()

class SmartRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Prevent automatic redirect consumption so we can inspect and capture redirect headers"""
    def http_error_302(self, req, fp, code, msg, headers):
        return fp
    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302

opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cookie_jar),
    urllib.request.HTTPSHandler(context=ssl_context),
    SmartRedirectHandler
)
urllib.request.install_opener(opener)

dynamic_portal_url = None

def load_config():
    """Load configuration and decrypt account credentials in memory"""
    if not os.path.exists(CONFIG_FILE):
        return "", []
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            portal_url = data.get("portal_url", "").strip()
            raw_accounts = data.get("accounts", [])
            accounts = []
            for acc in raw_accounts:
                u = acc.get("username", "").strip()
                p_enc = acc.get("password", "").strip()
                if u:
                    accounts.append({
                        "username": u,
                        "password": decrypt_password(p_enc)
                    })
            return portal_url, accounts
    except Exception:
        return "", []

def load_state():
    """Load rotation index and active cooldowns"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"current_index": 0, "cooldowns": {}}

def save_state(state):
    """Persist rotation state to disk"""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass

def check_network_status(portal_url_base):
    """
    Universal network status detector:
    - ONLINE: Internet connection is open and working
    - PORTAL_ACTIVE: Captive portal redirection intercepted
    - OFFLINE: Local network or gateway disconnected
    """
    global dynamic_portal_url
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CaptiveChecker/4.0"}

    for check_endpoint in (CHECK_URL, BACKUP_CHECK_URL):
        try:
            req = urllib.request.Request(check_endpoint, headers=headers)
            with opener.open(req, timeout=3) as response:
                if response.status == 204 or (response.status == 200 and b"Microsoft Connect Test" in response.read(64)):
                    dynamic_portal_url = None
                    return "ONLINE"

                location = response.headers.get("Location", "")
                if location:
                    dynamic_portal_url = location
                    return "PORTAL_ACTIVE"
        except Exception:
            pass

    # Optional manual fallback URL check
    if portal_url_base:
        try:
            req = urllib.request.Request(portal_url_base, headers=headers)
            with opener.open(req, timeout=3) as resp:
                if resp.status in (200, 302):
                    dynamic_portal_url = portal_url_base
                    return "PORTAL_ACTIVE"
        except Exception:
            pass

    return "OFFLINE"

def extract_form_tokens(page_html):
    """Extract hidden form inputs (CSRF tokens, session IDs, challenge tokens)"""
    tokens = {}
    try:
        inputs = re.findall(r'<input[^>]+type=["\']hidden["\'][^>]*>', page_html, re.IGNORECASE)
        for inp in inputs:
            name_match = re.search(r'name=["\']([^"\']+)["\']', inp, re.IGNORECASE)
            value_match = re.search(r'value=["\']([^"\']*)["\']', inp, re.IGNORECASE)
            if name_match and value_match:
                tokens[name_match.group(1)] = value_match.group(1)
    except Exception:
        pass
    return tokens

def fetch_login_page(target_url):
    """Fetch initial portal page to obtain session cookies and form tokens"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        req = urllib.request.Request(target_url, headers=headers)
        with opener.open(req, timeout=4) as res:
            content = res.read().decode("utf-8", errors="ignore")
            return target_url, content
    except Exception:
        return target_url, ""

def try_login(account, portal_url_base):
    """Submit authentication payload to the intercepted portal endpoint"""
    global dynamic_portal_url
    target_url = dynamic_portal_url if dynamic_portal_url else portal_url_base
    if not target_url:
        return "NO_URL"

    username = account.get("username", "").strip()
    password = account.get("password", "").strip()

    final_url, page_html = fetch_login_page(target_url)
    tokens = extract_form_tokens(page_html)

    payload = {
        "username": username,
        "password": password,
    }
    payload.update(tokens)

    encoded = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(final_url, data=encoded, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    req.add_header("Referer", final_url)

    try:
        with opener.open(req, timeout=6) as response:
            resp_body = response.read().decode("utf-8", errors="ignore").lower()
            limit_keywords = [
                "concurrent", "maximum", "online", "already logged", 
                "limit", "active session", "exceeded", "max users"
            ]
            if any(kw in resp_body for kw in limit_keywords):
                return "LIMIT_REACHED"
            return "SUCCESS"
    except Exception:
        return "SERVER_ERROR"

def handle_login_cycle(portal_url_base, accounts):
    """Execute round-robin authentication across available accounts"""
    total = len(accounts)
    if total == 0:
        return False

    state = load_state()
    start_index = state.get("current_index", 0) % total
    cooldowns = state.get("cooldowns", {})
    now = time.time()

    cooldowns = {user: t for user, t in cooldowns.items() if t > now}

    for attempt in range(total):
        idx = (start_index + attempt) % total
        acc = accounts[idx]
        user = acc.get("username")

        if user in cooldowns:
            continue

        result = try_login(acc, portal_url_base)

        if result == "LIMIT_REACHED":
            cooldowns[user] = now + COOLDOWN_TIME
            state["cooldowns"] = cooldowns
            save_state(state)
            continue

        time.sleep(3)

        if check_network_status(portal_url_base) == "ONLINE":
            state["current_index"] = (idx + 1) % total
            state["cooldowns"] = cooldowns
            save_state(state)
            return True
        else:
            time.sleep(1)

    state["current_index"] = (start_index + 1) % total
    state["cooldowns"] = cooldowns
    save_state(state)
    return False

def main():
    while True:
        try:
            portal_url_base, accounts = load_config()
            status = check_network_status(portal_url_base)

            if status == "PORTAL_ACTIVE":
                handle_login_cycle(portal_url_base, accounts)
                time.sleep(3)
            elif status == "ONLINE":
                time.sleep(CHECK_INTERVAL_ONLINE)
            else:
                time.sleep(CHECK_INTERVAL_OFFLINE)
        except Exception:
            time.sleep(3)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
