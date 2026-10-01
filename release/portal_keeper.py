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
DEBUG_LOG_FILE = os.path.join(BASE_DIR, "debug.log")

# Connectivity check endpoints (ultra-low bandwidth HTTP 204)
CHECK_URL = "http://connectivitycheck.gstatic.com/generate_204"
BACKUP_CHECK_URL = "http://www.msftconnecttest.com/connecttest.txt"

CHECK_INTERVAL_ONLINE = 15     # Sleep interval when connected (seconds)
CHECK_INTERVAL_OFFLINE = 5     # Check interval when disconnected (seconds)
COOLDOWN_TIME = 30             # Cooldown for accounts reaching concurrent connection limit (seconds)

def log_debug(msg):
    """Write timestamped diagnostic information to debug.log and stdout"""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

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

def find_config_file():
    """Locate accounts.json either locally or in LocalAppData"""
    candidates = [
        os.path.join(BASE_DIR, "accounts.json"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "AutoPortalKeeper", "accounts.json")
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return candidates[0]

def find_state_file():
    cfg = find_config_file()
    return os.path.join(os.path.dirname(cfg), "state.json")

def load_config():
    """Load configuration and decrypt account credentials in memory"""
    cfg_file = find_config_file()
    if not os.path.exists(cfg_file):
        log_debug(f"Config file not found in candidates: {cfg_file}")
        return "", []
    try:
        # Use utf-8-sig to automatically handle both UTF-8 with BOM and standard UTF-8
        with open(cfg_file, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            portal_url = data.get("portal_url", "").strip()
            if portal_url and not portal_url.startswith(("http://", "https://")):
                portal_url = "http://" + portal_url
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
            log_debug(f"Successfully loaded config from '{cfg_file}': accounts_count={len(accounts)}")
            return portal_url, accounts
    except Exception as e:
        log_debug(f"Error reading {cfg_file}: {e}")
        return "", []

def load_state():
    """Load rotation index and active cooldowns"""
    state_file = find_state_file()
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            pass
    return {"current_index": 0, "cooldowns": {}}

def save_state(state):
    """Persist rotation state to disk"""
    state_file = find_state_file()
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log_debug(f"Error saving state to {state_file}: {e}")

def check_network_status(portal_url_base):
    """
    Universal network status detector:
    - ONLINE: Internet connection is open and working (204 returned)
    - PORTAL_ACTIVE: Captive portal redirection intercepted
    - OFFLINE: Local network or gateway disconnected
    """
    global dynamic_portal_url
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CaptiveChecker/4.0"}

    for check_endpoint in (CHECK_URL, BACKUP_CHECK_URL):
        try:
            req = urllib.request.Request(check_endpoint, headers=headers)
            with opener.open(req, timeout=4) as response:
                status_code = getattr(response, "status", getattr(response, "code", 0))
                location = response.headers.get("Location", "")
                log_debug(f"Connectivity check to {check_endpoint} -> HTTP {status_code}, Location: '{location}'")

                if status_code == 204:
                    dynamic_portal_url = None
                    return "ONLINE"

                if status_code in (200, 301, 302, 303, 307) and location:
                    dynamic_portal_url = location
                    log_debug(f"Captured dynamic captive portal redirect: {dynamic_portal_url}")
                    return "PORTAL_ACTIVE"

                body_sample = response.read(256)
                if status_code == 200 and b"Microsoft Connect Test" in body_sample:
                    dynamic_portal_url = None
                    return "ONLINE"

                # If 200 is returned instead of 204 on generate_204, a captive portal intercepted the page
                if status_code == 200 and check_endpoint == CHECK_URL:
                    dynamic_portal_url = response.geturl() if hasattr(response, "geturl") else CHECK_URL
                    log_debug(f"Captive portal intercepted 204 page without redirect header. Target: {dynamic_portal_url}")
                    return "PORTAL_ACTIVE"
        except Exception as e:
            log_debug(f"Check failed on {check_endpoint}: {e}")

    # Optional manual fallback URL check
    if portal_url_base:
        try:
            log_debug(f"Testing manual portal fallback: {portal_url_base}")
            req = urllib.request.Request(portal_url_base, headers=headers)
            with opener.open(req, timeout=4) as resp:
                status_code = getattr(resp, "status", getattr(resp, "code", 0))
                log_debug(f"Manual portal fallback response: HTTP {status_code}")
                if status_code in (200, 301, 302, 303, 307):
                    dynamic_portal_url = portal_url_base
                    return "PORTAL_ACTIVE"
        except Exception as e:
            log_debug(f"Manual portal fallback unreachable: {e}")

    return "OFFLINE"

def fetch_login_page(target_url):
    """Fetch initial portal page to obtain session cookies and HTML form"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        log_debug(f"Fetching login page from: {target_url}")
        req = urllib.request.Request(target_url, headers=headers)
        with opener.open(req, timeout=6) as res:
            content = res.read().decode("utf-8", errors="ignore")
            actual_url = res.geturl() if hasattr(res, "geturl") else target_url
            log_debug(f"Login page fetched ({len(content)} bytes). Actual URL: {actual_url}")
            return actual_url, content
    except Exception as e:
        log_debug(f"Failed to fetch login page from {target_url}: {e}")
        return target_url, ""

def analyze_form(page_html, base_url):
    """
    Intelligently parse the captive portal HTML form:
    1. Finds form action URL and resolves relative paths to absolute URLs
    2. Dynamically detects username field name (user, username, txtUser, login, etc.)
    3. Dynamically detects password field name
    4. Extracts all hidden fields/tokens (CSRF, challenge tokens, session IDs)
    """
    action_url = base_url
    user_field = "username"
    pass_field = "password"
    hidden_payload = {}

    if not page_html:
        return action_url, user_field, pass_field, hidden_payload

    # Look for forms in HTML
    forms = re.findall(r'<form\b[^>]*>(.*?)</form>', page_html, re.IGNORECASE | re.DOTALL)
    target_form_html = page_html
    target_form_tag = ""

    # Prefer the form containing a password input
    form_tags = re.findall(r'(<form\b[^>]*>)', page_html, re.IGNORECASE)
    for idx, f_body in enumerate(forms):
        if re.search(r'type=["\']password["\']', f_body, re.IGNORECASE):
            target_form_html = f_body
            if idx < len(form_tags):
                target_form_tag = form_tags[idx]
            break

    # Extract action from form tag if found
    if target_form_tag:
        action_match = re.search(r'action=["\']([^"\']*)["\']', target_form_tag, re.IGNORECASE)
        if action_match and action_match.group(1).strip():
            raw_action = action_match.group(1).strip()
            action_url = urllib.parse.urljoin(base_url, raw_action)
            log_debug(f"Detected form action URL: {action_url} (from '{raw_action}')")

    # Extract all inputs
    inputs = re.findall(r'<input\b[^>]*>', target_form_html, re.IGNORECASE)
    log_debug(f"Found {len(inputs)} input tags in form")

    for inp in inputs:
        name_match = re.search(r'name=["\']([^"\']+)["\']', inp, re.IGNORECASE)
        type_match = re.search(r'type=["\']([^"\']+)["\']', inp, re.IGNORECASE)
        val_match = re.search(r'value=["\']([^"\']*)["\']', inp, re.IGNORECASE)

        if not name_match:
            continue

        inp_name = name_match.group(1)
        inp_type = type_match.group(1).lower() if type_match else "text"
        inp_val = val_match.group(1) if val_match else ""

        if inp_type == "password":
            pass_field = inp_name
            log_debug(f"Detected password input field: '{pass_field}'")
        elif inp_type in ("text", "email") or not type_match:
            name_lower = inp_name.lower()
            if any(k in name_lower for k in ("user", "login", "name", "email", "id", "account")):
                user_field = inp_name
                log_debug(f"Detected username input field: '{user_field}'")
        elif inp_type == "hidden":
            hidden_payload[inp_name] = inp_val
            log_debug(f"Captured hidden token: '{inp_name}' = '{inp_val[:30]}...'")

    return action_url, user_field, pass_field, hidden_payload

def try_login(account, portal_url_base):
    """Submit authentication payload to the dynamically parsed form action"""
    global dynamic_portal_url
    target_url = dynamic_portal_url if dynamic_portal_url else portal_url_base
    if not target_url:
        log_debug("No target portal URL available to submit login")
        return "NO_URL"

    username = account.get("username", "").strip()
    password = account.get("password", "").strip()

    actual_page_url, page_html = fetch_login_page(target_url)
    action_url, user_field, pass_field, hidden_payload = analyze_form(page_html, actual_page_url)

    payload = dict(hidden_payload)
    payload[user_field] = username
    payload[pass_field] = password

    masked_payload = {k: ("***" if k == pass_field else v) for k, v in payload.items()}
    log_debug(f"Submitting POST to: {action_url} with payload keys: {masked_payload}")

    encoded = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(action_url, data=encoded, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    req.add_header("Referer", actual_page_url)

    try:
        with opener.open(req, timeout=8) as response:
            status_code = getattr(response, "status", getattr(response, "code", 0))
            resp_body = response.read().decode("utf-8", errors="ignore")
            log_debug(f"POST response: HTTP {status_code}, length={len(resp_body)} bytes")
            log_debug(f"Response snippet: {resp_body[:250].strip()}")

            body_lower = resp_body.lower()
            limit_keywords = [
                "concurrent", "maximum", "online", "already logged", 
                "limit", "active session", "exceeded", "max users",
                "محدودیت", "تعداد متصل", "حداکثر", "کاربر آنلاین"
            ]
            if any(kw in body_lower for kw in limit_keywords):
                log_debug(f"Concurrent session limit detected for account '{username}'")
                return "LIMIT_REACHED"

            return "SUCCESS"
    except Exception as e:
        log_debug(f"Exception during login POST: {e}")
        return "SERVER_ERROR"

def handle_login_cycle(portal_url_base, accounts):
    """Execute round-robin authentication across available accounts"""
    total = len(accounts)
    if total == 0:
        log_debug("No accounts available in accounts.json")
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
            rem = int(cooldowns[user] - now)
            log_debug(f"Account '{user}' in cooldown ({rem}s remaining). Skipping...")
            continue

        log_debug(f"--- [Attempt {attempt + 1}/{total}] Trying account: '{user}' ---")
        result = try_login(acc, portal_url_base)

        if result == "LIMIT_REACHED":
            cooldowns[user] = now + COOLDOWN_TIME
            state["cooldowns"] = cooldowns
            save_state(state)
            continue

        # Wait briefly for gateway firewall to process session
        log_debug("Waiting 3s for gateway routing...")
        time.sleep(3)

        network_status = check_network_status(portal_url_base)
        log_debug(f"Post-login network verification status: {network_status}")

        if network_status == "ONLINE":
            log_debug(f"*** SUCCESS: Internet is now active on account '{user}'! ***")
            state["current_index"] = (idx + 1) % total
            state["cooldowns"] = cooldowns
            save_state(state)
            return True
        else:
            log_debug(f"Account '{user}' did not activate internet access. Moving to next account...")
            time.sleep(1)

    state["current_index"] = (start_index + 1) % total
    state["cooldowns"] = cooldowns
    save_state(state)
    log_debug("All accounts exhausted in this cycle without activating internet.")
    return False

def main():
    log_debug("==================================================")
    log_debug("AutoPortal Keeper Service Engine Started")
    log_debug("Developed by Raman Tondro (@RMNO21)")
    log_debug("==================================================")
    
    while True:
        try:
            portal_url_base, accounts = load_config()
            status = check_network_status(portal_url_base)
            log_debug(f"Heartbeat loop: Network Status = '{status}'")

            if status == "PORTAL_ACTIVE":
                log_debug("Captive portal detected! Initiating login cycle...")
                handle_login_cycle(portal_url_base, accounts)
                time.sleep(3)
            elif status == "ONLINE":
                time.sleep(CHECK_INTERVAL_ONLINE)
            else:
                time.sleep(CHECK_INTERVAL_OFFLINE)
        except Exception as e:
            log_debug(f"Unhandled exception in main loop: {e}")
            time.sleep(3)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log_debug("Service stopped by user.")
        sys.exit(0)
