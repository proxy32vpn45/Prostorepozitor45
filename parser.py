import asyncio
import base64
import json
import random
from urllib.parse import urlparse

import aiohttp

# =========================
# SOURCES
# =========================

SOURCE_SUBS = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt",
    "https://raw.githubusercontent.com/whoahaow/rjsxrd/refs/heads/main/githubmirror/bypass-unsecure/bypass-unsecure-all.txt",
    "https://raw.githubusercontent.com/Temnuk/naabuzil/refs/heads/main/whitelist_full",
    "https://raw.githubusercontent.com/zieng2/wl/main/vless_lite.txt",
    "https://cvedcsub.vercel.app/configs/configs.txt",
    "https://gist.githubusercontent.com/flaafix/raw/AetrisVPN.txt",
    "https://gitverse.ru/api/repos/flaafix/AetrisVPN/raw/branch/master/AetrisVPN.txt",
    "https://raw.githubusercontent.com/btsk161/Freeinternet_byMygalaru.github.io/refs/heads/main/premium.txt",
    "https://raw.githubusercontent.com/ShadowException/VPN/refs/heads/main/configs/VPN-cat-top-100",
    "https://gist.githubusercontent.com/nikitavalentinov90021-ai/raw/Premium.txt",
    "https://sub.pfvpn.cfd/free/sub",
    "https://etoneya.best/whitelist",
    "https://gitverse.ru/api/repos/bywarm/rser/raw/branch/master/selected.txt",
    "https://raw.githubusercontent.com/ByeWhiteLists/ByeWhiteLists2/refs/heads/main/ByeWhiteLists2.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_SS-all_RUS.txt",
    "https://sub.xexvpn.ru/sub-free-lte-full/A8AJT2UOK9/",
    "https://raw.githubusercontent.com/zieng2/wl/main/vless_universal.txt",
    "https://raw.githubusercontent.com/WSJuJuB01/WS_Parser/refs/heads/main/subscription.txt",
    "https://raw.githubusercontent.com/terik21/HiddifySubs-VlessKeys/refs/heads/main/WhiteKeys",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-CIDR-RU-checked.txt",
]

OUTPUT_FILE = "output.txt"

THREADS = 300
TIMEOUT = 1

REMOVE_DUPLICATES = True
AUTO_RENAME = True

SUPPORTED = [
    "vmess://",
    "vless://",
    "trojan://",
    "ss://",
]

# =========================
# MODES
# =========================

MODES = {
    "strict": {
        "max_latency": 800,
        "keep_dead": True,
    },
    "balanced": {
        "max_latency": 2500,
        "keep_dead": False,
    },
    "relaxed": {
        "max_latency": 8000,
        "keep_dead": False,
    },
}

MODE = "balanced"
mode = MODES[MODE]

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
    "TR": "🇹🇷",
    "PL": "🇵🇱",
}

FALLBACK = list(FLAGS.keys())

# =========================
# SCORE
# =========================

def score(latency, proto):
    if latency == 9999:
        return 0

    base = 1200 - latency

    if proto.startswith("vless://"):
        base += 60
    elif proto.startswith("vmess://"):
        base += 40
    elif proto.startswith("trojan://"):
        base += 30
    else:
        base += 10

    return max(base, 1)

# =========================
# FETCH
# =========================

async def fetch(session, url):
    try:
        async with session.get(url, timeout=20) as r:
            return await r.text()
    except Exception:
        return ""

# =========================
# BASE64
# =========================

def decode(text):
    try:
        decoded = base64.b64decode(text).decode()

        if any(proto in decoded for proto in SUPPORTED):
            return decoded

    except Exception:
        pass

    return text

# =========================
# EXTRACT
# =========================

def extract(text):
    return [
        line.strip()
        for line in text.splitlines()
        if any(line.startswith(proto) for proto in SUPPORTED)
    ]

# =========================
# HOST PARSER
# =========================

def get_host(cfg):
    try:
        if cfg.startswith("vmess://"):
            raw = cfg.replace("vmess://", "")
            raw += "=" * (-len(raw) % 4)

            data = json.loads(base64.b64decode(raw).decode())

            return (
                data.get("add"),
                int(data.get("port"))
            )

        parsed = urlparse(cfg)

        return (
            parsed.hostname,
            parsed.port
        )

    except Exception:
        return None, None

# =========================
# PING
# =========================

async def ping(host, port):
    try:
        loop = asyncio.get_running_loop()

        start = loop.time()

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=TIMEOUT
        )

        latency = int((loop.time() - start) * 1000)

        writer.close()
        await writer.wait_closed()

        return latency

    except Exception:
        return 9999

# =========================
# GEO
# =========================

async def geo(session, ip):
    try:
        async with session.get(
            f"http://ip-api.com/json/{ip}?fields=status,countryCode,city",
            timeout=5,
        ) as r:

            data = await r.json()

            if data.get("status") != "success":
                return random.choice(FALLBACK), "Node"

            country = data.get("countryCode") or random.choice(FALLBACK)
            city = data.get("city") or "Node"

            return country, city

    except Exception:
        return random.choice(FALLBACK), "Node"

# =========================
# RENAME
# =========================

def rename(cfg, index, country, city):
    base = cfg.split("#")[0]

    flag = FLAGS.get(country, "🏳️")

    return f"{base}#{index} {flag} {country} | {city}"

# =========================
# PROCESS
# =========================

async def process(session, sem, cfg, index):
    async with sem:

        host, port = get_host(cfg)

        if not host or not port:
            return None

        latency = await ping(host, port)

        if latency > mode["max_latency"]:
            if not mode["keep_dead"]:
                return None

        current_score = score(latency, cfg)

        if current_score <= 1 and not mode["keep_dead"]:
            return None

        country, city = await geo(session, host)

        if AUTO_RENAME:
            cfg = rename(cfg, index, country, city)

        return (
            current_score,
            latency,
            cfg,
        )

# =========================
# MAIN
# =========================

async def main():
    sem = asyncio.Semaphore(THREADS)

    connector = aiohttp.TCPConnector(
        limit=0,
        ssl=False
    )

    async with aiohttp.ClientSession(
        connector=connector
    ) as session:

        all_cfg = []

        for url in SOURCE_SUBS:
            text = await fetch(session, url)

            if not text:
                continue

            text = decode(text)

            all_cfg.extend(extract(text))

        if REMOVE_DUPLICATES:
            all_cfg = list(dict.fromkeys(all_cfg))

        print(f"FOUND: {len(all_cfg)}")

        tasks = [
            process(session, sem, cfg, i)
            for i, cfg in enumerate(all_cfg, start=1)
        ]

        results = await asyncio.gather(*tasks)

        good = [x for x in results if x]

        good.sort(
            key=lambda x: (-x[0], x[1])
        )

        final = [
            item[2]
            for item in good
        ]

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            f.write("\n".join(final))

        print(f"MODE: {MODE}")
        print(f"GOOD: {len(final)}")
        print(f"SAVED: {OUTPUT_FILE}")

# =========================
# RUN
# =========================

if __name__ == "__main__":
    asyncio.run(main())
