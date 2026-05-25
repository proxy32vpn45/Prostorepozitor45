
import asyncio
import base64
import json
import socket
from urllib.parse import urlparse, urlunparse

import aiohttp

# =========================
# SETTINGS
# =========================

SOURCE_SUBS = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt",
    "https://raw.githubusercontent.com/whoahaow/rjsxrd/refs/heads/main/githubmirror/bypass-unsecure/bypass-unsecure-all.txt",
    "https://raw.githubusercontent.com/Temnuk/naabuzil/refs/heads/main/whitelist_full",
    "https://raw.githubusercontent.com/zieng2/wl/main/vless_lite.txt",
    "https://cvedcsub.vercel.app/configs/configs.txt",
    "https://gist.githubusercontent.com/flaafix/c79a81037d15163360571c7a7331b153/raw/AetrisVPN.txt",
    "https://gitverse.ru/api/repos/flaafix/AetrisVPN/raw/branch/master/AetrisVPN.txt",
    "https://raw.githubusercontent.com/btsk161/Freeinternet_byMygalaru.github.io/refs/heads/main/premium.txt",
    "https://raw.githubusercontent.com/ShadowException/VPN/refs/heads/main/configs/VPN-cat-top-100",
    "https://gist.githubusercontent.com/nikitavalentinov90021-ai/5c0f36a8c7e078484a4c08fab5beee72/raw/8be7c44d7b264e3bf4119b031b4c5a96d7f306ca/Premium.txt",
    "https://raw.githubusercontent.com/ChkavHalyavaVPN/Chkav-HalyavaVPNUS-vpn-duo/refs/heads/main/vpn.txt",
    "https://gist.githubusercontent.com/pidarasuebisov-afk/e220b44264242d1a97c0908aba091edd/raw/PKN%20cocnyL",
    "https://sub.pfvpn.cfd/free/sub"
    
]

OUTPUT_FILE = "output.txt"

MAX_LATENCY = 5000
THREADS = 650
TIMEOUT = 5

REMOVE_DUPLICATES = True
REMOVE_DEAD = True
AUTO_RENAME = True
SORT_BY_LATENCY = True

SUPPORTED = [
    "vmess://",
    "vless://",
    "trojan://",
    "ss://"
]

# =========================
# FLAGS
# =========================

FLAGS = {
    "NL": "🇳🇱",
    "DE": "🇩🇪",
    "US": "🇺🇸",
    "FR": "🇫🇷",
    "GB": "🇬🇧",
    "RU": "🇷🇺",
    "JP": "🇯🇵",
    "SG": "🇸🇬",
    "CA": "🇨🇦",
    "TR": "🇹🇷"
}

# =========================
# DOWNLOAD
# =========================

async def fetch_text(session, url):
    try:
        async with session.get(url, timeout=20) as r:
            return await r.text()
    except:
        return ""

# =========================
# BASE64
# =========================

def decode_base64_if_needed(text):
    try:
        decoded = base64.b64decode(text).decode("utf-8")

        if any(x in decoded for x in SUPPORTED):
            return decoded

    except:
        pass

    return text

# =========================
# EXTRACT CONFIGS
# =========================

def extract_configs(text):
    configs = []

    for line in text.splitlines():
        line = line.strip()

        if any(line.startswith(x) for x in SUPPORTED):
            configs.append(line)

    return configs

# =========================
# VMESS
# =========================

def parse_vmess(config):
    try:
        raw = config.replace("vmess://", "")
        padded = raw + "=" * (-len(raw) % 4)

        decoded = base64.b64decode(padded).decode()

        return json.loads(decoded)

    except:
        return None

# =========================
# GET HOST
# =========================

def get_host_port(config):

    try:
        if config.startswith("vmess://"):

            data = parse_vmess(config)

            if not data:
                return None, None

            return data.get("add"), int(data.get("port"))

        parsed = urlparse(config)

        return parsed.hostname, parsed.port

    except:
        return None, None

# =========================
# GEOIP
# =========================

async def get_geo(session, ip):

    try:
        async with session.get(
            f"http://ip-api.com/json/{ip}?fields=countryCode,city",
            timeout=5
        ) as r:

            data = await r.json()

            return (
                data.get("countryCode", "UN"),
                data.get("city", "Unknown")
            )

    except:
        return "UN", "Unknown"

# =========================
# LATENCY
# =========================

async def tcp_ping(host, port):

    try:
        loop = asyncio.get_event_loop()

        start = loop.time()

        future = asyncio.open_connection(host, port)

        reader, writer = await asyncio.wait_for(
            future,
            timeout=TIMEOUT
        )

        latency = int((loop.time() - start) * 1000)

        writer.close()

        await writer.wait_closed()

        return latency

    except:
        return 9999

# =========================
# REMOVE OLD NAME
# =========================

def strip_name(config):

    if "#" in config:
        return config.split("#")[0]

    return config

# =========================
# AUTO RENAME
# =========================

def rename_config(config, index, country, city):

    base = strip_name(config)

    flag = FLAGS.get(country, "🏳️")

    name = f"{index} {flag} {country} {city}"

    return f"{base}#{name}"

# =========================
# VALIDATION
# =========================

def invalid_host(host):

    if not host:
        return True

    bad = [
        "127.",
        "0.0.0.0",
        "localhost"
    ]

    for x in bad:
        if host.startswith(x):
            return True

    return False

# =========================
# CHECK CONFIG
# =========================

async def process_config(session, semaphore, config, index):

    async with semaphore:

        host, port = get_host_port(config)

        if invalid_host(host):
            return None

        latency = await tcp_ping(host, port)

        if latency > MAX_LATENCY:
            return None

        country, city = await get_geo(session, host)

        if AUTO_RENAME:
            config = rename_config(
                config,
                index,
                country,
                city
            )

        return (
            latency,
            config
        )

# =========================
# MAIN
# =========================

async def main():

    semaphore = asyncio.Semaphore(THREADS)

    async with aiohttp.ClientSession() as session:

        all_configs = []

        for sub in SOURCE_SUBS:

            text = await fetch_text(session, sub)

            text = decode_base64_if_needed(text)

            all_configs.extend(
                extract_configs(text)
            )

        if REMOVE_DUPLICATES:
            all_configs = list(set(all_configs))

        tasks = []

        for i, config in enumerate(all_configs, start=1):

            tasks.append(
                process_config(
                    session,
                    semaphore,
                    config,
                    i
                )
            )

        results = await asyncio.gather(*tasks)

        good = []

        for r in results:
            if r:
                good.append(r)

        if SORT_BY_LATENCY:
            good.sort(key=lambda x: x[0])

        final = [x[1] for x in good]

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            f.write("\n".join(final))

        print(f"GOOD CONFIGS: {len(final)}")

# =========================
# RUN
# =========================

asyncio.run(main())
