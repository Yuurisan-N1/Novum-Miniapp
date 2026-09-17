<div align="center">

<img width="100%" alt="header" src="https://capsule-render.vercel.app/api?type=waving&height=210&text=Novum%20Miniapp%20Bot&fontAlign=50&fontAlignY=36&fontSize=56&desc=Auto%20Login%20%7C%20Auto%20Gift%20%7C%20Auto%20Mining%20Claim%20%7C%20Proxy%20Support&descAlign=50&descAlignY=58"/>

<img alt="typing" src="https://readme-typing-svg.demolab.com?font=Inter&size=18&duration=3000&pause=650&center=true&vCenter=true&width=900&lines=Auto+Mining+%7C+Accrued+Profit+Claimed+Above+The+Platform+Minimum;Auto+Gift+Box+%7C+Opened+Until+The+Daily+Boxes+Are+Gone;Auto+Channel+Bonus+%7C+Claimed+Once+The+Subscription+Is+Confirmed;Referral+Monitoring+%7C+Next+Level+Progress+In+The+Log;Session+Cache+%7C+Claiming+Keeps+Running+After+initData+Expires;Proxy+Support+%7C+Multi-Account"/>

<p>
  <img alt="python" src="https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white"/>
  <img alt="platform" src="https://img.shields.io/badge/Platform-NOVUM.AI%20Agent-111111"/>
  <img alt="multi-account" src="https://img.shields.io/badge/Multi--Account-Supported-111111"/>
  <img alt="proxy" src="https://img.shields.io/badge/Proxy-Supported-111111"/>
  <img alt="author" src="https://img.shields.io/badge/by-Yuurisandesu-111111"/>
</p>

<p>
  <b>Novum AI Bot</b> is a full automation bot for the NOVUM.AI Agent Telegram Miniapp.<br/>
  It handles the complete cycle for every account: verifying the account with its <code>initData</code>, caching a consistent device identity together with the session cookie the server issues so the account keeps claiming after its <code>initData</code> expires, reporting the account profile, claiming the accrued mining profit as long as it stays above the minimum of the platform, opening all daily gift boxes, claiming the telegram channel bonus when the subscription is confirmed, and reporting the referral progress of every account, all running automatically across multiple accounts with proxy support, masked proxy logging, and a live countdown between cycles.<br/>
  Built and distributed by <b>Yuurisandesu</b>.
</p>

</div>

---

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Bot](#running-the-bot)
- [Features](#features)
- [File Structure](#file-structure)
- [Disclaimer](#disclaimer)

---

## Requirements

- Python `3.12+`
- Git

---

## Installation

**Clone the repository:**

```bash
git clone https://github.com/Yuurisan-N1/Novum-Miniapp.git
cd Novum-Miniapp
```

**Install dependencies:**

```bash
pip install aiohttp yuurisan
```

---

## Configuration

### 1. Accounts (data.txt)

Fill `data.txt` with Telegram WebApp `initData` for each account, one per line:

```
user=%7B%22id%22...&hash=abc123
user=%7B%22id%22...&hash=def456
```

> `initData` can be obtained from the browser DevTools when opening NOVUM.AI Agent on Telegram Web.
> The identifier of every account lives in the `initData` body, so the raw line is enough. Accounts are processed sequentially, and one blank line is printed between accounts to keep the log readable.

### 2. Proxy (proxy.txt)

Fill `proxy.txt` with proxies, one per line (optional, leave empty to run without proxy):

```
host:port
host:port:user:pass
http://user:pass@host:port
```

Proxies are assigned to accounts by index in round-robin order, so when there are fewer proxies than accounts the same proxy is reused for the remaining accounts. When `proxy.txt` is missing or empty the bot runs without any proxy. Credentials are never printed, the log only shows a masked form such as `http://user:pass@74*****81:10000`.

### 3. Bot Settings (config.json)

`sleep_seconds` controls how many seconds the bot waits between cycles. If `config.json` is missing, the bot falls back to a default of `3600` seconds.

### 4. Device Identity and Session Cache (device.json)

`device.json` is created automatically on the first run and is never part of the download. It stores one record per Telegram account, keyed by the telegram id, holding the cached device identifier together with the device fingerprint that was used the first time the account logged in, plus the session cookie the server issued for that account. Every later run reuses the same record, so the account always reports a consistent device and the server device rule stays satisfied. When the `initData` of an account is no longer accepted by the server, the bot falls back to the stored session cookie and keeps claiming for as long as that cookie is still valid, so a line only has to be refreshed once the cookie expires too. Delete the file only when a fresh device identity and a fresh session are really wanted.

> `device.json` holds a live session cookie, so treat it like a credential and never share it.

---

## Running the Bot

```bash
python bot.py
```

Press `Ctrl+C` at any time to stop the bot cleanly.

---

## Features

### Account Loading
Every line of `data.txt` is one account. The bot authenticates by posting the `initData` to the bootstrap endpoint, caches the session cookie the server issues in `device.json`, and logs the account username, coin balance, USDT balance, mining level and referral count before doing any work. When the server rejects the `initData`, the cached session cookie of that account is loaded instead and the account keeps running without a fresh line, which is reported once in the log.

### Device Identity Cache
The device identifier, the full device fingerprint and the session cookie are generated and captured once per account and cached in `device.json` next to the telegram id. The cache works silently and keeps every account stable across restarts.

### Auto Mining
The bot reads the mining state from the login response first and reports the accrued profit together with how many cycles were used out of the daily limit. Every remaining cycle is then claimed in order. A claim is only reported in green after the server confirms it, and the credited USDT is taken from the balance difference of the response, so nothing is reported that the server did not really credit. A profit that is still below the minimum of the platform, a claim refused by the server, and a claim that is still cooling down are each reported once in yellow instead of being retried blindly. An account that runs on its cached session cookie reads the mining state from the claim answer of the server itself.

### Auto Gift Box
The bot reads the gift box state and opens every box left for the day. Each box is reported with the prize the server returned, which may be USDT, extra mining cycles or bonus coins, and the run closes with the total number of boxes opened.

### Auto Channel Bonus
The bot checks the channel bonus status and claims the bonus only when the server reports the subscription as confirmed, then reports the credited coins. A bonus that is already claimed stays silent in the log, a missing channel subscription is reported once in yellow, and the telegram channel join itself is never attempted by the bot.

### Referral Monitoring
The distance to the next referral level is read from the server and reported together with the coins that level pays, and the referral list is reported with the number of entries it holds.

### Profile Statistics
The profile statistics are read and reported when the server sends a real value.

### Final Balance Pass
After all features are done the bot reads the fresh account state once more and prints the final coin and USDT balance for the account. An account that already runs on its cached session cookie closes on the state of the last confirmed answer of the server.

### Multi Account
All accounts in `data.txt` are processed sequentially within every cycle, with one blank line between accounts so every account block stays easy to read.

### Proxy Support
Proxies are loaded from `proxy.txt`, normalized to a full URL and assigned to accounts by position in round-robin order. Proxy credentials are masked in log output. Running without proxies is fully supported.

### Auto Countdown
After all accounts complete a cycle, the bot displays a live `HH:MM:SS` countdown in place until the next cycle starts, then prints the banner again and begins the next cycle.

---

## File Structure

```text
Novum-Miniapp/
├── bot.py          # Main bot, full cycle automation
├── config.json     # Sleep duration between cycles
├── data.txt        # Account initData, one per line
├── proxy.txt       # Proxy list, one per line (optional)
├── LICENSE         # License file
└── utils/
    └── banner.py   # Banner using yuurisan module
```

---

## Disclaimer

This tool is built for educational and technical exploration purposes. Use it wisely and at your own responsibility.

---

<div align="center">
<img width="100%" alt="footer" src="https://capsule-render.vercel.app/api?type=waving&height=120&section=footer"/>
</div>
