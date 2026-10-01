# AutoPortal Keeper 🌐⚡

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6.svg?logo=windows)](https://microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.x-3776AB.svg?logo=python)](https://www.python.org/)
[![C#](https://img.shields.io/badge/C%23-.NET%20Framework%204.x-239120.svg?logo=csharp)](https://dotnet.microsoft.com/)
[![Developer](https://img.shields.io/badge/Developer-Raman%20Tondro%20(@RMNO21)-brightgreen.svg?logo=github)](https://github.com/RMNO21)

> **Universal, silent, and resilient background captive portal auto-login & account rotation service for Windows.**  
> Makes captive portal networks (universities, dormitories, colleges, hotels, and enterprise Wi-Fi) behave like seamless home Wi-Fi.

---

## 🌟 Key Highlights

- **Instant Event-Driven Triggers (Kernel-Level):** Integrated directly with the Windows IP Helper API (`iphlpapi.NotifyAddrChange`) and monotonic clock jump listeners. Whenever a Wi-Fi adapter connects, roams between campus access points, receives a new DHCP lease, or wakes from sleep/hibernation, the daemon is interrupted in **< 10 milliseconds** without waiting for polling timers.
- **Universal Captive Interceptor:** Automatically detects and captures dynamic HTTP 302 redirections, extracting session tokens, IP queries, and MAC parameters in real-time. Works across MikroTik, Cisco, Fortinet, pfSense, Huawei, and custom institutional portals without hardcoded domain dependencies.
- **Military-Grade Credential Protection (Windows DPAPI):** Passwords are never saved in plaintext. Credentials are encrypted at the OS level using native `CryptProtectData` (Windows Data Protection API) tied exclusively to your user profile.
- **Smart Round-Robin Rotation:** Seamlessly rotates through configured accounts on every reconnection session to balance data usage, prevent quota exhaustion, and distribute network traffic.
- **Rapid Concurrent Limit Failover:** If an account hits a maximum simultaneous device limit (`Concurrent Session Limit`), the service gracefully switches to the next available account within seconds and applies a brief 30-second cooldown.
- **Zero-Resource Silent Daemon:** Runs completely headless via native VBScript/Python. No command prompt popups, no distracting notifications, no unnecessary disk log writes, and virtually 0% CPU consumption.
- **Bilingual Native Installer & Uninstaller:** Features a polished, multi-step Windows Forms wizard (`Setup.exe`) with real-time English and Persian language switching, plus a clean one-click `Uninstall.exe`.

---

## 🏗️ Architecture & How It Works

```
                +---------------------------------+
                |   Windows Boots / Wi-Fi Connect |
                +---------------------------------+
                                |
                                v
               [ HTTP 204 Connectivity Check ]
                                |
        +-----------------------+-----------------------+
        |                                               |
  HTTP 204 OK                                 HTTP 302 Redirect
  (Internet Active)                           (Captive Portal Intercepted)
        |                                               |
        v                                               v
[ Sleep 15s ] (0% CPU)                   [ Capture Dynamic Portal URL ]
                                                        |
                                                        v
                                          [ Windows DPAPI Decrypt (RAM) ]
                                                        |
                                                        v
                                          [ Submit Login Payload (POST) ]
                                                        |
                                +-----------------------+-----------------------+
                                |                                               |
                          Login Success                               Concurrent Limit / Error
                                |                                               |
                                v                                               v
                     [ Save Next Account Index ]                   [ 30s Cooldown & Try Next ]
```

1. **Lightweight Heartbeat:** While connected, the engine sends an ultra-low bandwidth (~200 bytes) request to standard connectivity check endpoints every 15 seconds.
2. **Redirection Capture:** When an unauthenticated captive portal hijacks the request, the engine extracts the full target URL (including router session query strings).
3. **In-Memory Decryption:** Passwords encrypted with Windows DPAPI are decrypted strictly in memory using standard library `ctypes` without saving temporary plaintext files.
4. **Session Handoff:** Once internet connectivity is verified, the pointer automatically advances to the next account for the next session.

---

## 🚀 Installation & Usage

### Option 1: Quick Installer (Recommended)

1. Download or clone this repository.
2. Open the `release` folder (or run `release/Setup.exe`).
3. Follow the wizard steps:
   - **Step 1:** Select preferred language (**English** or **فارسی**).
   - **Step 2:** Review overview & startup configuration.
   - **Step 3:** Enter Portal URL (Optional — leave blank to auto-detect any captive portal).
   - **Step 4:** Add your accounts (Usernames & Passwords). Passwords will be encrypted automatically.
   - **Step 5:** Click **Install**.
4. The service will immediately start in the background and register with Windows Startup.

### Option 2: Clean Uninstallation

- Run `Uninstall.exe` from the Start Menu (`Programs > AutoPortal Keeper`) or from `%LOCALAPPDATA%\AutoPortalKeeper\Uninstall.exe`.
- It cleanly stops background processes, removes startup shortcuts, and deletes application files.

---

## 🛠️ Building from Source

The setup wizard and uninstaller are written in pure C# using Windows Forms and compile using the native `csc.exe` compiler pre-installed on every Windows system.

Run the one-click build script:

```cmd
build.bat
```

This compiles:
- `src/Installer.cs` ➔ `release/Setup.exe`
- `src/Uninstaller.cs` ➔ `release/Uninstall.exe`
- Copies `src/portal_keeper.py` ➔ `release/portal_keeper.py`

---

## 🔒 Security & Privacy

- **No Plaintext Passwords:** Credentials in `accounts.json` are stored as base64 ciphertext protected by the Windows Cryptographic subsystem. They cannot be deciphered on another computer or by another user account.
- **No Telemetry / No Tracking:** Zero external network calls. The only outbound HTTP requests are your portal login and connectivity verification checks.
- **No Log Clutter:** Disables persistent disk logging to minimize SSD wear and prevent credential leakage.

---

## 👤 Author & Developer

- **Name:** Raman Tondro (رامان تندرو)
- **GitHub:** [@RMNO21](https://github.com/RMNO21)
- **Email:** tondroraman83@gmail.com
- **Website:** [RMNO21.github.io](https://RMNO21.github.io)

---

## 📄 License

This project is open-source and released under the [MIT License](LICENSE).
Copyright (c) 2026 Raman Tondro.
