import os
import sys
import json
import time
import random
import signal
import asyncio
import aiohttp
import yarl
import urllib.parse

from utils.banner import show_banner

RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"

MY_PROJECT = "Novum AI Miniapp"
BASE_URL = "https://ainexus.one"
REF_CODE = "6004380466"

BOOT_ATTEMPTS = 5
BOOT_RETRY_SECONDS = 4
CLAIM_ATTEMPTS = 4
CLAIM_RETRY_SECONDS = 5
DEVICE_FILE = "device.json"
SESSION_COOKIE = "astra.tg.sid"

BANNED_CODES = (
    91, 93, 124, 35, 33, 64, 36, 37, 94, 38, 42, 40, 41,
    45, 44, 58, 59, 39, 34, 96, 126, 43, 61, 60, 62, 63, 47, 92,
)
BANNED_CHARS = tuple(chr(code) for code in BANNED_CODES)

BUSY_CODES = ("busy", "sqlite_busy", "rate_limited")
BUSY_STATUS = (429, 502, 503, 504)
REFUSED_CODES = ("initdata_expired", "initdata_invalid", "invalid_initdata", "session_expired", "unauthorized")

HEADERS_BASE = {
    "accept": "*/*",
    "accept-encoding": "identity",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "no-cache",
    "content-type": "application/json",
    "origin": BASE_URL,
    "pragma": "no-cache",
    "priority": "u=1, i",
    "referer": f"{BASE_URL}/",
    "sec-ch-ua": '"Microsoft Edge";v="152", "Not?A_Brand";v="24", "Chromium";v="152", "Microsoft Edge WebView2";v="152"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"Android"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Mobile Safari/537.36",
}

DEVICE_CACHE = {}
SESSION_MODE = {}


def log_green(msg):
    print(f"{GREEN}{BOLD}{msg}{RESET}")


def log_yellow(msg):
    print(f"{YELLOW}{BOLD}{msg}{RESET}")


def log_red(msg):
    print(f"{RED}{BOLD}{msg}{RESET}")


def signal_handler(sig, frame):
    print()
    log_red("Script stopped by user")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def load_config():
    defaults = {"settings": {"sleep_seconds": 3600}}
    if not os.path.exists("config.json"):
        return defaults
    try:
        with open("config.json") as handle:
            return json.load(handle)
    except Exception:
        return defaults


def load_data():
    if not os.path.exists("data.txt"):
        log_red("File data.txt was not found")
        sys.exit(1)
    lines = [line.strip() for line in open("data.txt").readlines() if line.strip()]
    if not lines:
        log_red("File data.txt is empty")
        sys.exit(1)
    return lines


def load_proxies():
    if not os.path.exists("proxy.txt"):
        return []
    try:
        return [line.strip() for line in open("proxy.txt").readlines() if line.strip()]
    except Exception:
        return []


def get_proxy(proxies, index):
    if not proxies:
        return None
    return proxies[index % len(proxies)]


def normalize_proxy(proxy_line):
    if not proxy_line:
        return None
    value = proxy_line.strip()
    if "://" in value:
        return value
    parts = value.split(":")
    if len(parts) == 4:
        host, port, user, password = parts
        return f"http://{user}:{password}@{host}:{port}"
    if len(parts) == 3:
        host, port, user = parts
        return f"http://{user}@{host}:{port}"
    return f"http://{value}"


def mask_proxy(proxy_url):
    try:
        value = proxy_url.split("://")[-1]
        after_at = value.split("@")[-1]
        host_part = after_at.split(":")[0]
        port_part = after_at.split(":")[1] if ":" in after_at else ""
        octets = host_part.split(".")
        if len(octets) == 4:
            masked_host = f"{octets[0]}*****{octets[3]}"
        elif len(host_part) > 4:
            masked_host = f"{host_part[:2]}*****{host_part[-2:]}"
        else:
            masked_host = "***"
        suffix = f":{port_part}" if port_part else ""
        return f"http://user:pass@{masked_host}{suffix}"
    except Exception:
        return "http://user:pass@***:***"


def clean_text(value, fallback):
    text = str(value)
    for symbol in BANNED_CHARS:
        text = text.replace(symbol, " ")
    text = " ".join(text.split())
    return text if text else str(fallback)


def unit_word(value, singular, plural):
    return singular if int(value) == 1 else plural


def round_text(value, digits=8):
    try:
        return f"{round(float(value), int(digits))}"
    except Exception:
        return "0"


def countdown(seconds):
    for remaining in range(int(seconds), 0, -1):
        h = remaining // 3600
        m = (remaining % 3600) // 60
        s = remaining % 60
        print(f"\r{YELLOW}{BOLD}Next cycle starts in {h:02d}:{m:02d}:{s:02d}{RESET}", end="", flush=True)
        time.sleep(1)
    print()


def init_data_fields(init_data):
    try:
        return dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return {}


def parse_init_data(init_data):
    fields = init_data_fields(init_data)
    try:
        return json.loads(fields.get("user") or "{}")
    except Exception:
        return {}


def load_device_cache():
    global DEVICE_CACHE
    DEVICE_CACHE = {}
    if not os.path.exists(DEVICE_FILE):
        return
    try:
        with open(DEVICE_FILE) as handle:
            parsed = json.load(handle)
    except Exception:
        log_red("Device cache was unreadable so it will be rewritten")
        return
    if isinstance(parsed, dict):
        DEVICE_CACHE = parsed


def save_device_cache():
    try:
        with open(DEVICE_FILE, "w") as handle:
            json.dump(DEVICE_CACHE, handle, indent=2, sort_keys=True)
    except Exception:
        log_red("The device cache could not be written to disk")


def cached_session(account_id):
    entry = DEVICE_CACHE.get(str(account_id))
    if isinstance(entry, dict):
        session = entry.get("session")
        if isinstance(session, dict) and session.get("cookie"):
            return str(session["cookie"])
    return ""


def cache_session(account_id, cookie_value):
    account_id = str(account_id)
    if not account_id or not cookie_value:
        return
    entry = DEVICE_CACHE.get(account_id)
    if not isinstance(entry, dict):
        return
    session = entry.get("session")
    if isinstance(session, dict) and session.get("cookie") == cookie_value:
        return
    entry["session"] = {"cookie": cookie_value, "saved_at": int(time.time())}
    save_device_cache()


def session_cookie(session):
    try:
        for morsel in session.cookie_jar:
            if morsel.key == SESSION_COOKIE:
                return str(morsel.value)
    except Exception:
        return ""
    return ""


def apply_session_cookie(session, cookie_value):
    try:
        session.cookie_jar.update_cookies({SESSION_COOKIE: cookie_value}, response_url=yarl.URL(BASE_URL))
        return True
    except Exception:
        return False


def device_identity(init_data, user_info):
    account_id = str(user_info.get("id") or "")
    entry = DEVICE_CACHE.get(account_id)
    if isinstance(entry, dict) and entry.get("device_id"):
        return entry

    fields = init_data_fields(init_data)
    random_hex = "".join(random.choice("0123456789abcdef") for _ in range(24))
    seed = int(random_hex[:6], 16)
    record = {
        "id": account_id,
        "username": str(user_info.get("username") or user_info.get("first_name") or ""),
        "device_id": f"dev_{random_hex}",
        "platform": "android",
        "timezone_offset_minutes": -int(time.timezone / 60) if time.timezone else 0,
        "registration_duration_ms": 1200 + seed % 2600,
        "device_data": {
            "user_agent": HEADERS_BASE["user-agent"],
            "language": str(user_info.get("language_code") or "en"),
            "hardware_concurrency": 4 + seed % 5,
            "device_memory": 4 + seed % 5,
            "max_touch_points": 5,
            "screen_width": 360 + seed % 133,
            "screen_height": 720 + seed % 300,
            "screen_color_depth": 24,
            "device_pixel_ratio": round(2 + (seed % 200) / 100, 2),
            "timezone": str(time.tzname[0] if time.tzname else "UTC"),
            "canvas_hash": "",
            "webgl_unmasked_vendor": "",
            "webgl_unmasked_renderer": "",
            "tg_platform": "android",
            "chat_instance": str(fields.get("chat_instance") or "")[:128],
        },
    }
    if isinstance(entry, dict) and isinstance(entry.get("session"), dict):
        record["session"] = entry["session"]
    DEVICE_CACHE[account_id] = record
    save_device_cache()
    return record


def error_code(payload):
    if isinstance(payload, dict):
        return str(payload.get("code") or "")
    return ""


def busy_error(status, payload):
    if status in BUSY_STATUS:
        return True
    if isinstance(payload, dict):
        if error_code(payload) in BUSY_CODES:
            return True
        message = str(payload.get("message") or payload.get("error") or "").lower()
        if "busy" in message or "загружен" in message:
            return True
    return False


def refused_error(status, payload):
    if status == 401:
        return True
    return error_code(payload) in REFUSED_CODES


async def api(session, method, endpoint, payload=None, proxy=None):
    try:
        async with session.request(
            method,
            f"{BASE_URL}{endpoint}",
            headers=dict(HEADERS_BASE),
            json=payload,
            proxy=proxy,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            raw = await response.read()
            try:
                data = json.loads(raw)
            except Exception:
                data = None
            return response.status, data
    except Exception as error:
        log_red(f"Request to {clean_text(endpoint, 'endpoint')} failed with {clean_text(type(error).__name__, 'Error')}")
        return None, None


async def init_data_login(session, account_id, body, proxy):
    delay = BOOT_RETRY_SECONDS
    for attempt in range(BOOT_ATTEMPTS):
        status, payload = await api(session, "POST", "/api/bootstrap", body, proxy)
        if status == 200 and isinstance(payload, dict) and payload.get("user"):
            return payload
        if status == 403 or error_code(payload) in ("farm_bot_device", "account_blocked"):
            log_red("This account was blocked by the server device rule")
            SESSION_MODE[account_id] = "blocked"
            return None
        if refused_error(status, payload):
            return None
        if not busy_error(status, payload):
            return None
        if attempt < BOOT_ATTEMPTS - 1:
            await asyncio.sleep(delay)
            delay += BOOT_RETRY_SECONDS
    return None


async def cookie_login(session, account_id, proxy):
    stored = cached_session(account_id)
    if not stored or not apply_session_cookie(session, stored):
        return None
    delay = BOOT_RETRY_SECONDS
    for attempt in range(CLAIM_ATTEMPTS):
        status, payload = await api(session, "POST", "/api/mining/claim", {"action": "claim_cycle"}, proxy)
        if status == 200 and isinstance(payload, dict) and payload.get("user"):
            cache_session(account_id, session_cookie(session))
            return payload
        if busy_error(status, payload):
            await asyncio.sleep(delay)
            delay += BOOT_RETRY_SECONDS
            continue
        return None
    return None


async def bootstrap(session, init_data, proxy):
    user_info = parse_init_data(init_data)
    account_id = str(user_info.get("id") or "")
    identity = device_identity(init_data, user_info)

    if SESSION_MODE.get(account_id) != "cookie":
        body = {
            "initData": init_data,
            "platform": identity.get("platform") or "unknown",
            "referrer": REF_CODE,
            "timezone_offset_minutes": identity.get("timezone_offset_minutes", 0),
            "language_code": str(user_info.get("language_code") or "en")[:8],
            "device_data": identity.get("device_data") or {},
            "registration_duration_ms": identity.get("registration_duration_ms", 0),
        }
        state = await init_data_login(session, account_id, body, proxy)
        if state:
            cache_session(account_id, session_cookie(session))
            SESSION_MODE[account_id] = "initdata"
            return state
        if SESSION_MODE.get(account_id) == "blocked":
            return None

    state = await cookie_login(session, account_id, proxy)
    if state and SESSION_MODE.get(account_id) != "cookie":
        SESSION_MODE[account_id] = "cookie"
        log_yellow("Init data was rejected so the cached session cookie was used")
    return state


def balance_usdt(state):
    return float((state or {}).get("user", {}).get("usdt_balance") or 0)


async def run_mining(session, state, proxy):
    mining = (state or {}).get("mining") or {}
    cycles_left = int(mining.get("cycles_left") or 0)
    cycles_used = int(mining.get("cycles_used") or 0)
    per_day = int(mining.get("level_cycles_per_day") or mining.get("cycles_limit") or 0)
    pending = mining.get("pending_profit_usdt") or 0

    if cycles_left <= 0:
        log_yellow(f"All {clean_text(per_day, 0)} daily mining cycles are already used")
        return state

    log_green(f"Mining accrued {clean_text(round_text(pending), 0)} USDT with {clean_text(cycles_used, 0)} of {clean_text(per_day, 0)} cycles used")

    claimed_cycles = 0
    claimed_usdt = 0.0
    while claimed_cycles < cycles_left:
        before = balance_usdt(state)
        status, payload = await api(session, "POST", "/api/mining/claim", {"action": "claim_cycle"}, proxy)
        if status == 200 and isinstance(payload, dict):
            fresh_mining = payload.get("mining") or {}
            pending = fresh_mining.get("pending_profit_usdt") or 0
            minimum = payload.get("min_claim_usdt") or fresh_mining.get("min_claim_usdt") or 0
            if payload.get("claimed"):
                state = payload
                reward = balance_usdt(payload) - before
                claimed_cycles += 1
                claimed_usdt += reward
                log_green(f"Mining cycle paid {clean_text(round_text(reward), 0)} USDT with {clean_text(state.get('user', {}).get('coins_balance'), 0)} coins held")
                if int(fresh_mining.get("cycles_left") or 0) <= 0:
                    break
                await asyncio.sleep(1)
                continue
            if payload.get("below_min"):
                log_yellow(f"Mining profit is below the {clean_text(minimum, 0)} USDT minimum")
                return state
            log_yellow("Mining claim was refused by the server on this run")
            return state
        if status == 403 or error_code(payload) == "profit_claim_cooldown":
            log_yellow("Mining claim is still cooling down on the server")
            return state
        if busy_error(status, payload) and claimed_cycles < CLAIM_ATTEMPTS:
            await asyncio.sleep(CLAIM_RETRY_SECONDS)
            continue
        break

    if claimed_cycles:
        log_green(f"{clean_text(claimed_cycles, 0)} mining {unit_word(claimed_cycles, 'cycle was', 'cycles were')} claimed and {clean_text(round_text(claimed_usdt), 0)} USDT was credited")
    return state


async def run_gift_box(session, proxy):
    status, state = await api(session, "GET", "/api/gift-box/state", None, proxy)
    if status != 200 or not isinstance(state, dict):
        log_yellow("Gift box state could not be retrieved on this run")
        return

    box = state.get("box") or {}
    boxes_left = int(box.get("boxes_left") or 0)
    quota = int(box.get("daily_quota") or 0)

    if boxes_left <= 0:
        log_yellow("Gift boxes for today were already opened for this account")
        return

    log_yellow(f"Gift box has {clean_text(boxes_left, 0)} of {clean_text(quota, 0)} boxes left for today")

    opened = 0
    while boxes_left > 0:
        status, payload = await api(session, "POST", "/api/gift-box/open", None, proxy)
        if status != 200 or not isinstance(payload, dict):
            if busy_error(status, payload):
                await asyncio.sleep(CLAIM_RETRY_SECONDS)
                continue
            log_yellow("Gift box could not be opened on this run")
            return
        prize = payload.get("prize") or {}
        kind = str(prize.get("type") or "").lower()
        amount = prize.get("amount") or 0
        if kind == "usdt":
            log_green(f"Gift box paid {clean_text(round_text(amount), 0)} USDT")
        elif kind == "cycles":
            log_green(f"Gift box paid {clean_text(amount, 0)} extra mining cycles")
        else:
            log_green(f"Gift box paid {clean_text(amount, 0)} coins")
        opened += 1
        box = payload.get("box") or {}
        boxes_left = int(box.get("boxes_left") or 0)
        if boxes_left > 0:
            await asyncio.sleep(1)

    if opened:
        log_green(f"{clean_text(opened, 0)} gift {unit_word(opened, 'box was', 'boxes were')} opened for this account")


async def run_channel_bonus(session, proxy):
    status, state = await api(session, "GET", "/api/channel-bonus/status", None, proxy)
    if status != 200 or not isinstance(state, dict):
        log_yellow("Channel bonus status could not be retrieved on this run")
        return
    if state.get("claimed"):
        return
    if not state.get("available"):
        log_yellow("Channel bonus needs a confirmed channel subscription first")
        return

    status, payload = await api(session, "POST", "/api/channel-bonus/claim", None, proxy)
    if status == 200 and isinstance(payload, dict):
        if payload.get("already_claimed"):
            return
        log_green(f"Channel bonus paid {clean_text(payload.get('bonus_coins'), 0)} coins and {clean_text(payload.get('bonus_usdt'), 0)} USDT")
        return
    if error_code(payload) == "not_subscribed":
        log_yellow("Channel bonus needs a confirmed channel subscription first")
        return
    log_yellow("Channel bonus claim was refused by the server on this run")


async def run_referral(session, proxy):
    status, payload = await api(session, "GET", "/api/referral/me", None, proxy)
    if status != 200 or not isinstance(payload, dict):
        log_yellow("Referral state could not be retrieved on this run")
        return

    referral = payload.get("referral") or {}
    count = int(referral.get("referrals_count") or 0)
    needed = int(referral.get("needed_for_next") or 0)
    bonus = referral.get("next_level_bonus") or referral.get("next_invite_bonus") or 0
    if needed > 0:
        log_yellow(f"Next level needs {clean_text(needed, 0)} more {unit_word(needed, 'friend', 'friends')} for {clean_text(bonus, 0)} coins")

    status, listing = await api(session, "GET", "/api/referral/list", None, proxy)
    if status == 200 and isinstance(listing, dict):
        items = listing.get("referrals") or []
        if isinstance(items, list) and items:
            log_green(f"Referral list holds {clean_text(len(items), 0)} {unit_word(len(items), 'entry', 'entries')} for this account")


async def run_stats(session, proxy):
    status, payload = await api(session, "GET", "/api/profile/stats", None, proxy)
    if status != 200 or not isinstance(payload, dict):
        return
    stats = payload.get("stats") or {}
    if not stats:
        return
    earned = stats.get("earned_usdt") or stats.get("total_earned_usdt") or 0
    if earned:
        log_yellow(f"Profile statistics show {clean_text(round_text(earned), 0)} USDT earned in total")


async def process_account(init_data, proxy, index):
    user_info = parse_init_data(init_data)
    if not user_info.get("id"):
        log_red(f"Account on line {clean_text(index, 1)} holds invalid initData and was skipped")
        return

    connector = aiohttp.TCPConnector(ssl=False)
    jar = aiohttp.CookieJar(unsafe=True)
    async with aiohttp.ClientSession(connector=connector, cookie_jar=jar) as session:
        state = await bootstrap(session, init_data, proxy)
        if not state:
            log_red("Login failed for this account")
            return

        user = state.get("user") or {}
        if user.get("is_banned"):
            log_red("Account is banned and was skipped")
            return

        log_green(f"Account {clean_text(user.get('username') or user.get('first_name'), 'Unknown')} loaded successfully")
        log_green(f"Balance is {clean_text(user.get('coins_balance'), 0)} coins and {clean_text(user.get('usdt_balance'), 0)} USDT")

        referrals = int(user.get("referrals_count") or 0)
        log_green(f"Mining level {clean_text(user.get('mining_level'), 1)} with {clean_text(referrals, 0)} {unit_word(referrals, 'invited friend', 'invited friends')}")

        if float(user.get("referral_earned_usdt") or 0) > 0:
            log_green(f"Referral earnings added {clean_text(round_text(user.get('referral_earned_usdt')), 0)} USDT to this account")

        state = await run_mining(session, state, proxy)
        await run_gift_box(session, proxy)
        await run_channel_bonus(session, proxy)
        await run_referral(session, proxy)
        await run_stats(session, proxy)

        if SESSION_MODE.get(str(user.get("telegram_id") or "")) != "cookie":
            refreshed = await bootstrap(session, init_data, proxy)
            if refreshed:
                state = refreshed

        final_user = state.get("user") or {}
        log_green(f"Final balance is {clean_text(final_user.get('coins_balance'), 0)} coins and {clean_text(final_user.get('usdt_balance'), 0)} USDT")


async def main_async(accounts, proxies, sleep_secs):
    cycle = 1
    while True:
        log_yellow(f"Starting automation cycle number {clean_text(cycle, 0)}")

        for index, init_data in enumerate(accounts):
            if index > 0:
                print()

            proxy_line = get_proxy(proxies, index)
            proxy_url = normalize_proxy(proxy_line) if proxy_line else None
            if proxy_url:
                log_yellow(f"Using proxy {mask_proxy(proxy_url)}")

            await process_account(init_data, proxy_url, index + 1)

        log_yellow(f"Automation cycle number {clean_text(cycle, 0)} is complete")
        cycle += 1
        countdown(sleep_secs)
        show_banner(MY_PROJECT)


def main():
    show_banner(MY_PROJECT)

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    config = load_config()
    sleep_secs = config.get("settings", {}).get("sleep_seconds", 3600)
    accounts = load_data()
    proxies = load_proxies()
    load_device_cache()
    asyncio.run(main_async(accounts, proxies, sleep_secs))


if __name__ == "__main__":
    main()
