"""
====================================================================
AutoPortal Keeper - Ultra-Fast Reactive Engine (v6.0)
Developed by: Raman Tondro
GitHub: https://github.com/RMNO21
License: MIT
====================================================================
Features:
1. Native Windows Kernel IPHLPAPI NotifyAddrChange + WlanRegisterNotification triggers.
2. Concurrent multi-endpoint latency-free captive portal probing.
3. Fast socket-level fallback with local gateway redirection interception.
4. Auto-login on system boot, user logon, wake-from-sleep, and Wi-Fi roaming.
5. In-memory DPAPI credential decryption with zero disk leakage.
6. Zero UI flicker / silent background execution with < 0.1% CPU consumption.
====================================================================
"""

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import ctypes
from ctypes import wintypes
import http.cookiejar
from html.parser import HTMLParser
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "accounts.json")
STATE_FILE = os.path.join(BASE_DIR, "state.json")
DEBUG_LOG_FILE = os.path.join(BASE_DIR, "debug.log")

# Primary probe endpoints
PROBE_ENDPOINTS = [
    ("http://connectivitycheck.gstatic.com/generate_204", 204),
    ("http://www.msftconnecttest.com/connecttest.txt", 200),
    ("http://captive.apple.com/hotspot-detect.html", 200)
]

# High-performance tuning parameters
ONLINE_HEARTBEAT_SEC = 2.0      # Active heartbeat when connected (seconds)
OFFLINE_RETRY_SEC = 0.5         # Instant retry interval when offline/authenticating (seconds)
HTTP_TIMEOUT = 2.0              # Timeout for form fetching & post
PROBE_TIMEOUT = 1.0             # Fast timeout per probe endpoint
COOLDOWN_TIME = 30              # Account concurrency cooldown

# Global synchronization event for immediate wake-up on system network events
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

# ==============================================================================
# Security: Native Windows DPAPI (tied to current user profile)
# ==============================================================================

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

# ==============================================================================
# HTTP Opener Setup (SSL-tolerant & Non-Consuming Redirects)
# ==============================================================================

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

# ==============================================================================
# Configuration & State Management
# ==============================================================================

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
# Network Helper Utilities
# ==============================================================================

def get_default_gateway():
    """Dynamically get current default IPv4 gateway"""
    try:
        flags = 0
        if sys.platform == "win32":
            flags = 0x08000000  # CREATE_NO_WINDOW
        out = subprocess.check_output("route print 0.0.0.0", text=True, creationflags=flags)
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
                return parts[2]
    except Exception:
        pass
    return None

# ==============================================================================
# OS Event Triggers: Hardware Network Change & Sleep/Resume & WLAN Callbacks
# ==============================================================================

def windows_network_change_listener():
    """
    Native Windows Kernel Trigger 1:
    Uses IPHLPAPI NotifyAddrChange to detect network adapter connect, disconnect,
    IP assignment, gateway change, or Wi-Fi roaming in < 10 milliseconds.
    """
    try:
        iphlpapi = ctypes.windll.iphlpapi
        hand = wintypes.HANDLE()
        log_debug("OS Kernel Trigger: Network event listener active.")
        while True:
            iphlpapi.NotifyAddrChange(ctypes.byref(hand), None)
            log_debug("⚡ [OS Trigger] Hardware Network Interface / IP Change detected! Waking up immediately...")
            wake_event.set()
            time.sleep(0.1)
    except Exception as e:
        log_debug(f"Network change listener exception: {e}")

def windows_wlan_listener():
    """
    Native Windows Kernel Trigger 2:
    Subscribes directly to Windows Native WLAN API (wlanapi.dll) notification stream.
    Fires instantaneously upon BSSID connection, association, or disconnect events.
    """
    try:
        wlanapi = ctypes.windll.wlanapi
        client_handle = wintypes.HANDLE()
        negotiated_version = wintypes.DWORD()
        ret = wlanapi.WlanOpenHandle(2, None, ctypes.byref(negotiated_version), ctypes.byref(client_handle))
        if ret != 0:
            return

        WLAN_NOTIFICATION_SOURCE_ACM = 0x00000008
        WLAN_NOTIFICATION_SOURCE_MSM = 0x00000010
        WLAN_NOTIFICATION_CALLBACK = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)

        @WLAN_NOTIFICATION_CALLBACK
        def on_notification(data_ptr, context_ptr):
            wake_event.set()

        prev_source = wintypes.DWORD()
        ret_reg = wlanapi.WlanRegisterNotification(
            client_handle,
            WLAN_NOTIFICATION_SOURCE_ACM | WLAN_NOTIFICATION_SOURCE_MSM,
            False,
            on_notification,
            None,
            None,
            ctypes.byref(prev_source)
        )
        if ret_reg == 0:
            log_debug("OS Native WLAN Trigger: WlanRegisterNotification active.")
            while True:
                time.sleep(60.0)
    except Exception as e:
        log_debug(f"WLAN listener exception: {e}")

def sleep_resume_detector():
    """
    System Resume / Lid-Open Trigger:
    Detects when laptop wakes up from sleep or hibernation by tracking monotonic clock jumps.
    """
    last_tick = time.monotonic()
    while True:
        time.sleep(0.5)
        current_tick = time.monotonic()
        if current_tick - last_tick > 2.0:
            log_debug("⚡ [OS Trigger] System Wake-from-Sleep / Resume detected! Triggering instant verification...")
            wake_event.set()
        last_tick = current_tick

threading.Thread(target=windows_network_change_listener, daemon=True, name="NetChangeTrigger").start()
threading.Thread(target=windows_wlan_listener, daemon=True, name="WlanEventTrigger").start()
threading.Thread(target=sleep_resume_detector, daemon=True, name="SleepResumeTrigger").start()

# ==============================================================================
# Robust HTML Form Parser
# ==============================================================================

class CaptiveFormParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.action_url = base_url
        self.user_field = "username"
        self.pass_field = "password"
        self.hidden_payload = {}
        self.in_form = False
        self.current_form_has_password = False
        self.current_form_action = base_url
        self.current_inputs = []

    def handle_starttag(self, tag, attrs):
        attr_dict = {k.lower(): v for k, v in attrs if v is not None}
        if tag.lower() == "form":
            self.in_form = True
            raw_action = attr_dict.get("action", "")
            self.current_form_action = urllib.parse.urljoin(self.base_url, raw_action) if raw_action else self.base_url
            self.current_form_has_password = False
            self.current_inputs = []
        elif self.in_form and tag.lower() == "input":
            name = attr_dict.get("name")
            itype = attr_dict.get("type", "text").lower()
            val = attr_dict.get("value", "")
            if name:
                self.current_inputs.append((name, itype, val))
                if itype == "password":
                    self.current_form_has_password = True

    def handle_endtag(self, tag):
        if tag.lower() == "form" and self.in_form:
            if self.current_form_has_password or not self.hidden_payload:
                self.action_url = self.current_form_action
                for name, itype, val in self.current_inputs:
                    if itype == "password":
                        self.pass_field = name
                    elif itype in ("text", "email"):
                        if any(k in name.lower() for k in ("user", "login", "name", "account", "id")):
                            self.user_field = name
                    elif itype == "hidden":
                        self.hidden_payload[name] = val
            self.in_form = False

def parse_portal_form(page_html, base_url):
    """Parse HTML form action, user/pass fields, and hidden tokens"""
    if not page_html:
        return base_url, "username", "password", {}
    try:
        parser = CaptiveFormParser(base_url)
        parser.feed(page_html)
        return parser.action_url, parser.user_field, parser.pass_field, parser.hidden_payload
    except Exception as e:
        log_debug(f"HTMLParser error: {e}, falling back to defaults")
        return base_url, "username", "password", {}

# ==============================================================================
# Ultra-Fast Concurrent Multi-Tier Network & Captive Portal Verification
# ==============================================================================

def check_single_endpoint(endpoint_tuple):
    """Worker function for concurrent connectivity probing"""
    url, exp_code = endpoint_tuple
    req = urllib.request.Request(url, headers={"User-Agent": "CaptiveProber/6.0"})
    with opener.open(req, timeout=PROBE_TIMEOUT) as resp:
        code = getattr(resp, "status", getattr(resp, "code", 0))
        loc = resp.headers.get("Location", "")
        if loc:
            return "PORTAL_ACTIVE", loc
        if code in (301, 302, 303, 307):
            return "PORTAL_ACTIVE", resp.headers.get("Location", "")
        body = resp.read(128)
        if code == 204 and exp_code == 204:
            return "ONLINE", None
        if b"Microsoft Connect Test" in body or b"Success" in body:
            return "ONLINE", None
        return "PORTAL_ACTIVE", resp.geturl()

def check_network_status(portal_url_base):
    """
    High-Speed Captive Portal & Network Status Detector:
    Returns:
    - 'ONLINE': Internet is active
    - 'PORTAL_ACTIVE': Captive portal interception confirmed
    - 'OFFLINE': Network/interface disconnected or transitioning
    """
    global dynamic_portal_url

    # Tier 1: Concurrent Probing of Standard Captive Endpoints (takes ~300-600ms)
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(check_single_endpoint, ep) for ep in PROBE_ENDPOINTS]
            for f in as_completed(futures):
                try:
                    res_status, res_loc = f.result()
                    if res_status == "ONLINE":
                        dynamic_portal_url = None
                        return "ONLINE"
                    elif res_status == "PORTAL_ACTIVE":
                        if res_loc:
                            dynamic_portal_url = res_loc
                        return "PORTAL_ACTIVE"
                except Exception:
                    pass
    except Exception:
        pass

    # Tier 2: Gateway Hotspot Redirection Interception
    gw_ip = get_default_gateway()
    if gw_ip:
        try:
            gw_url = f"http://{gw_ip}/"
            req = urllib.request.Request(gw_url, headers={"User-Agent": "CaptiveProber/6.0"})
            with opener.open(req, timeout=1.0) as resp:
                loc = resp.headers.get("Location", "")
                if loc and ("login" in loc.lower() or "status" in loc.lower() or "hotspot" in loc.lower()):
                    target = loc
                    if "/status" in target:
                        target = target.replace("/status", "/login")
                    dynamic_portal_url = target
                    log_debug(f"Gateway {gw_ip} returned captive redirect: '{loc}' -> Target: '{dynamic_portal_url}'")
                    return "PORTAL_ACTIVE"
        except Exception:
            pass

    # Tier 3: Check configured manual portal URL
    if portal_url_base:
        try:
            req = urllib.request.Request(portal_url_base, headers={"User-Agent": "CaptiveProber/6.0"})
            with opener.open(req, timeout=1.2) as resp:
                code = getattr(resp, "status", getattr(resp, "code", 0))
                if code in (200, 301, 302, 303, 307):
                    dynamic_portal_url = portal_url_base
                    return "PORTAL_ACTIVE"
        except Exception:
            pass

    # Tier 4: Direct Gateway TCP socket liveness check
    # If gateway port 80/53 responds, we have link-layer connectivity and captive portal interception
    if gw_ip:
        for port in (80, 53):
            s = socket.socket()
            s.settimeout(0.5)
            try:
                s.connect((gw_ip, port))
                s.close()
                log_debug(f"Gateway {gw_ip}:{port} reachable. Captive portal present.")
                if not dynamic_portal_url and portal_url_base:
                    dynamic_portal_url = portal_url_base
                return "PORTAL_ACTIVE"
            except Exception:
                try:
                    s.close()
                except Exception:
                    pass

    return "OFFLINE"

# ==============================================================================
# Authentication & Rotation Engine
# ==============================================================================

def fetch_login_page(target_url):
    """Fetch login page HTML to extract tokens, form action, and session cookies"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        req = urllib.request.Request(target_url, headers=headers)
        with opener.open(req, timeout=HTTP_TIMEOUT) as res:
            content = res.read().decode("utf-8", errors="ignore")
            actual_url = res.geturl() if hasattr(res, "geturl") else target_url
            return actual_url, content
    except Exception as e:
        log_debug(f"Failed to fetch login page from {target_url}: {e}")
        return target_url, ""

def try_login(account, portal_url_base):
    """Submit authentication payload to the captive portal"""
    global dynamic_portal_url
    target_url = dynamic_portal_url if dynamic_portal_url else portal_url_base
    if not target_url:
        return "NO_URL"

    username = account.get("username", "").strip()
    password = account.get("password", "").strip()

    actual_page_url, page_html = fetch_login_page(target_url)
    action_url, user_field, pass_field, hidden_payload = parse_portal_form(page_html, actual_page_url)

    payload = dict(hidden_payload)
    payload[user_field] = username
    payload[pass_field] = password

    log_debug(f"Submitting credentials for '{username}' to: {action_url}")
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
    """Execute rapid round-robin authentication across configured accounts"""
    total = len(accounts)
    if total == 0:
        log_debug("No accounts available for login.")
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
            log_debug(f"Skipping '{user}' (cooldown active).")
            continue

        log_debug(f"🚀 Rapid Login Attempt [{attempt + 1}/{total}] with '{user}'...")
        result = try_login(acc, portal_url_base)

        if result == "LIMIT_REACHED":
            cooldowns[user] = now + COOLDOWN_TIME
            state["cooldowns"] = cooldowns
            save_state(state)
            continue

        # Fast 0.8s wait for router NAT/firewall state table update
        time.sleep(0.8)

        # Immediate verification
        if check_network_status(portal_url_base) == "ONLINE":
            log_debug(f"✅ Authenticated successfully! Account '{user}' activated internet access.")
            state["current_index"] = (idx + 1) % total
            state["cooldowns"] = cooldowns
            save_state(state)
            return True
        else:
            log_debug(f"Account '{user}' did not grant internet access. Switching immediately to next...")
            time.sleep(0.2)

    state["current_index"] = (start_index + 1) % total
    state["cooldowns"] = cooldowns
    save_state(state)
    return False

# ==============================================================================
# Main Event Loop
# ==============================================================================

def main():
    log_debug("==================================================")
    log_debug("AutoPortal Keeper v6.0 - High-Performance Reactive Engine")
    log_debug("Developed by Raman Tondro (@RMNO21)")
    log_debug("==================================================")

    last_logged_status = None
    heartbeat_counter = 0

    while True:
        try:
            was_triggered = wake_event.is_set()
            wake_event.clear()

            portal_url_base, accounts = load_config()
            status = check_network_status(portal_url_base)

            if status != last_logged_status or was_triggered or heartbeat_counter % 20 == 0:
                trigger_info = " [Woken by OS Event Trigger]" if was_triggered else ""
                log_debug(f"Network Status = '{status}'{trigger_info}")
                last_logged_status = status

            heartbeat_counter += 1

            if status == "PORTAL_ACTIVE":
                log_debug("⚡ Captive portal active! Firing instant authentication...")
                success = handle_login_cycle(portal_url_base, accounts)
                if not success:
                    wake_event.wait(timeout=1.0)
            elif status == "ONLINE":
                # Sleep adaptively: exits instantly (<10ms) if any OS network event occurs, or after 2s
                wake_event.wait(timeout=ONLINE_HEARTBEAT_SEC)
            else:
                wake_event.wait(timeout=OFFLINE_RETRY_SEC)

        except Exception as e:
            log_debug(f"Loop exception: {e}")
            time.sleep(0.5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
