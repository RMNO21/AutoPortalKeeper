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
import threading
import time
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "accounts.json")
STATE_FILE = os.path.join(BASE_DIR, "state.json")
DEBUG_LOG_FILE = os.path.join(BASE_DIR, "debug.log")

# Endpoints for ultra-fast connectivity check
CHECK_URL = "http://connectivitycheck.gstatic.com/generate_204"
BACKUP_CHECK_URL = "http://www.msftconnecttest.com/connecttest.txt"

# Ultra-fast intervals (Event-driven with adaptive heartbeat)
ONLINE_HEARTBEAT_SEC = 5.0     # Adaptive interval when connected (seconds)
OFFLINE_RETRY_SEC = 2.0        # Rapid retry interval when offline (seconds)
COOLDOWN_TIME = 30             # Cooldown for accounts reaching concurrent connection limit (seconds)
HTTP_TIMEOUT = 3.0             # Fast network timeout (seconds)

# Global synchronization event for instant wakeups on OS network triggers
wake_event = threading.Event()

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
        return "", []
    try:
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

# ==============================================================================
# OS Event Triggers: Hardware Network Change & Sleep/Resume Listeners
# ==============================================================================

def windows_network_change_listener():
    """
    Native Windows Kernel Trigger:
    Uses IPHLPAPI NotifyAddrChange to detect network adapter connect, disconnect,
    IP assignment, gateway change, or Wi-Fi roaming in < 10 milliseconds.
    Consumes 0% CPU by sleeping inside the Windows kernel wait queue.
    """
    try:
        iphlpapi = ctypes.windll.iphlpapi
        hand = wintypes.HANDLE()
        log_debug("OS Kernel Trigger: Network event listener active.")
        while True:
            # Blocks until network interface or routing table changes
            iphlpapi.NotifyAddrChange(ctypes.byref(hand), None)
            log_debug("⚡ [OS Trigger] Hardware Network Interface / IP Change detected! Waking up immediately...")
            wake_event.set()
            time.sleep(0.3)
    except Exception as e:
        log_debug(f"Network change listener exception: {e}")

def sleep_resume_detector():
    """
    System Resume / Lid-Open Trigger:
    Detects when laptop wakes up from sleep or hibernation by tracking monotonic clock jumps.
    """
    last_tick = time.monotonic()
    while True:
        time.sleep(1.0)
        current_tick = time.monotonic()
        # If monotonic time jumped more than 3 seconds over a 1-second sleep, PC was asleep
        if current_tick - last_tick > 3.5:
            log_debug("⚡ [OS Trigger] System Wake-from-Sleep / Resume detected! Triggering instant verification...")
            wake_event.set()
        last_tick = current_tick

# Start native background trigger threads
threading.Thread(target=windows_network_change_listener, daemon=True, name="NetChangeTrigger").start()
threading.Thread(target=sleep_resume_detector, daemon=True, name="SleepResumeTrigger").start()

# ==============================================================================
# Network Verification & Captive Portal Interception
# ==============================================================================

def check_network_status(portal_url_base):
    """
    Fast universal status detector:
    - ONLINE: Internet connection is open and working (204 returned)
    - PORTAL_ACTIVE: Captive portal redirection intercepted
    - OFFLINE: Local network or gateway disconnected
    """
    global dynamic_portal_url
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CaptiveChecker/5.0"}

    for check_endpoint in (CHECK_URL, BACKUP_CHECK_URL):
        try:
            req = urllib.request.Request(check_endpoint, headers=headers)
            with opener.open(req, timeout=HTTP_TIMEOUT) as response:
                status_code = getattr(response, "status", getattr(response, "code", 0))
                location = response.headers.get("Location", "")

                if status_code == 204:
                    dynamic_portal_url = None
                    return "ONLINE"

                if status_code in (200, 301, 302, 303, 307) and location:
                    dynamic_portal_url = location
                    log_debug(f"Captured dynamic portal redirect: {dynamic_portal_url}")
                    return "PORTAL_ACTIVE"

                body_sample = response.read(256)
                if status_code == 200 and b"Microsoft Connect Test" in body_sample:
                    dynamic_portal_url = None
                    return "ONLINE"

                if status_code == 200 and check_endpoint == CHECK_URL:
                    dynamic_portal_url = response.geturl() if hasattr(response, "geturl") else CHECK_URL
                    log_debug(f"Portal intercepted without redirect header. Target: {dynamic_portal_url}")
                    return "PORTAL_ACTIVE"
        except Exception:
            pass

    # Fallback to manual portal URL if specified
    if portal_url_base:
        try:
            req = urllib.request.Request(portal_url_base, headers=headers)
            with opener.open(req, timeout=HTTP_TIMEOUT) as resp:
                status_code = getattr(resp, "status", getattr(resp, "code", 0))
                if status_code in (200, 301, 302, 303, 307):
                    dynamic_portal_url = portal_url_base
                    return "PORTAL_ACTIVE"
        except Exception:
            pass

    return "OFFLINE"

def fetch_login_page(target_url):
    """Fetch initial portal page to obtain session cookies and HTML form"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        req = urllib.request.Request(target_url, headers=headers)
        with opener.open(req, timeout=HTTP_TIMEOUT) as res:
            content = res.read().decode("utf-8", errors="ignore")
            actual_url = res.geturl() if hasattr(res, "geturl") else target_url
            return actual_url, content
    except Exception:
        return target_url, ""

def analyze_form(page_html, base_url):
    """
    Intelligently parse the captive portal HTML form:
    1. Finds form action URL and resolves relative paths to absolute URLs
    2. Dynamically detects username field name
    3. Dynamically detects password field name
    4. Extracts all hidden fields/tokens (CSRF, challenge tokens, session IDs)
    """
    action_url = base_url
    user_field = "username"
    pass_field = "password"
    hidden_payload = {}

    if not page_html:
        return action_url, user_field, pass_field, hidden_payload

    forms = re.findall(r'<form\b[^>]*>(.*?)</form>', page_html, re.IGNORECASE | re.DOTALL)
    target_form_html = page_html
    target_form_tag = ""

    form_tags = re.findall(r'(<form\b[^>]*>)', page_html, re.IGNORECASE)
    for idx, f_body in enumerate(forms):
        if re.search(r'type=["\']password["\']', f_body, re.IGNORECASE):
            target_form_html = f_body
            if idx < len(form_tags):
                target_form_tag = form_tags[idx]
            break

    if target_form_tag:
        action_match = re.search(r'action=["\']([^"\']*)["\']', target_form_tag, re.IGNORECASE)
        if action_match and action_match.group(1).strip():
            raw_action = action_match.group(1).strip()
            action_url = urllib.parse.urljoin(base_url, raw_action)

    inputs = re.findall(r'<input\b[^>]*>', target_form_html, re.IGNORECASE)
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
        elif inp_type in ("text", "email") or not type_match:
            name_lower = inp_name.lower()
            if any(k in name_lower for k in ("user", "login", "name", "email", "id", "account")):
                user_field = inp_name
        elif inp_type == "hidden":
            hidden_payload[inp_name] = inp_val

    return action_url, user_field, pass_field, hidden_payload

def try_login(account, portal_url_base):
    """Submit authentication payload to the dynamically parsed form action"""
    global dynamic_portal_url
    target_url = dynamic_portal_url if dynamic_portal_url else portal_url_base
    if not target_url:
        return "NO_URL"

    username = account.get("username", "").strip()
    password = account.get("password", "").strip()

    actual_page_url, page_html = fetch_login_page(target_url)
    action_url, user_field, pass_field, hidden_payload = analyze_form(page_html, actual_page_url)

    payload = dict(hidden_payload)
    payload[user_field] = username
    payload[pass_field] = password

    encoded = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(action_url, data=encoded, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    req.add_header("Referer", actual_page_url)

    try:
        with opener.open(req, timeout=HTTP_TIMEOUT) as response:
            resp_body = response.read().decode("utf-8", errors="ignore").lower()
            limit_keywords = [
                "concurrent", "maximum", "online", "already logged", 
                "limit", "active session", "exceeded", "max users",
                "محدودیت", "تعداد متصل", "حداکثر", "کاربر آنلاین"
            ]
            if any(kw in resp_body for kw in limit_keywords):
                log_debug(f"Account '{username}' reached concurrent device limit.")
                return "LIMIT_REACHED"

            return "SUCCESS"
    except Exception as e:
        log_debug(f"Login POST exception for '{username}': {e}")
        return "SERVER_ERROR"

def handle_login_cycle(portal_url_base, accounts):
    """Execute high-speed round-robin authentication across available accounts"""
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

        log_debug(f"🚀 Rapid Login Attempt [{attempt + 1}/{total}] with '{user}'...")
        result = try_login(acc, portal_url_base)

        if result == "LIMIT_REACHED":
            cooldowns[user] = now + COOLDOWN_TIME
            state["cooldowns"] = cooldowns
            save_state(state)
            continue

        # Fast 1.2 second wait for gateway routing tables to update
        time.sleep(1.2)

        if check_network_status(portal_url_base) == "ONLINE":
            log_debug(f"✅ Authenticated successfully! Account '{user}' activated internet access.")
            state["current_index"] = (idx + 1) % total
            state["cooldowns"] = cooldowns
            save_state(state)
            return True
        else:
            log_debug(f"Account '{user}' did not grant internet access. Switching immediately to next...")
            time.sleep(0.5)

    state["current_index"] = (start_index + 1) % total
    state["cooldowns"] = cooldowns
    save_state(state)
    return False

def main():
    log_debug("==================================================")
    log_debug("AutoPortal Keeper v4.0 - Ultra-Fast Event-Driven Engine")
    log_debug("Developed by Raman Tondro (@RMNO21)")
    log_debug("==================================================")

    last_logged_status = None
    heartbeat_counter = 0

    while True:
        try:
            # Clear trigger flag for this cycle
            was_triggered = wake_event.is_set()
            wake_event.clear()

            portal_url_base, accounts = load_config()
            status = check_network_status(portal_url_base)

            # Log status when it changes, or periodically every 60s, or when woken by a hardware trigger
            if status != last_logged_status or was_triggered or heartbeat_counter % 12 == 0:
                trigger_info = " [Woken by OS Event Trigger]" if was_triggered else ""
                log_debug(f"Network Status = '{status}'{trigger_info}")
                last_logged_status = status

            heartbeat_counter += 1

            if status == "PORTAL_ACTIVE":
                log_debug("⚡ Captive portal active! Firing instant authentication...")
                handle_login_cycle(portal_url_base, accounts)
                wake_event.wait(timeout=1.0)
            elif status == "ONLINE":
                # Sleep adaptively: exits instantly (<10ms) if any OS network event occurs, or after 5s
                wake_event.wait(timeout=ONLINE_HEARTBEAT_SEC)
            else:
                wake_event.wait(timeout=OFFLINE_RETRY_SEC)

        except Exception as e:
            log_debug(f"Loop exception: {e}")
            time.sleep(1.0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
