import asyncio
import base64
import json
import aiohttp
import random
from urllib.parse import urlparse

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
    "https://sub.pfvpn.cfd/free/sub"
]

OUTPUT_FILE = "output.txt"

THREADS = 300
TIMEOUT = 1

REMOVE_DUPLICATES = True
AUTO_RENAME = True

SUPPORTED = ["vmess://", "vless://", "trojan://", "ss://"]

# =========================
# MODES (NEW SYSTEM)
# =========================

MODES = {
    "strict": {
        "max_latency": 800,
        "keep_dead": True
    },
    "balanced": {
        "max_latency": 2500,
        "keep_dead": False
    },
    "relaxed": {
        "max_latency": 8000,
        "keep_dead": False
    }
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
    "PL": "🇵🇱"
}

FALLBACK = list(FLAGS.keys())

# =========================
# SCORE SYSTEM
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
    except:
        return ""

# =========================
# BASE64
# =========================

def decode(text):
    try:
        d = base64.b64decode(text).decode()
        if any(x in d for x in SUPPORTED):
            return d
    except:
        pass
    return text

# =========================
# EXTRACT
# =========================

def extract(text):
    return [x.strip() for x in text.splitlines() if any(x.startswith(s) for s in SUPPORTED)]

# =========================
# HOST PARSER
# =========================

def get_host(cfg):

    try:
        if cfg.startswith("vmess://"):
            raw = cfg.replace("vmess://", "")
            raw += "=" * (-len(raw) % 4)
            data = json.loads(base64.b64decode(raw).decode())
            return data.get("add"), int(data.get("port"))

        u = urlparse(cfg)
        return u.hostname, u.port

    except:
        return None, None

# =========================
# PING
# =========================

async def ping(host, port):

    try:
        loop = asyncio.get_event_loop()
        start = loop.time()

        r, w = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=TIMEOUT
        )

        ms = int((loop.time() - start) * 1000)

        w.close()
        await w.wait_closed()

        return ms

    except:
        return 9999

# =========================
# GEO (FALLBACK SAFE)
# =========================

async def geo(session, ip):

    try:
        async with session.get(
            f"http://ip-api.com/json/{ip}?fields=status,countryCode,city",
            timeout=5
        ) as r:

            d = await r.json()

            if d.get("status") != "success":
                return random.choice(FALLBACK), "Node"

            c = d.get("countryCode") or random.choice(FALLBACK)
            city = d.get("city") or "Node"

            return c, city

    except:
        return random.choice(FALLBACK), "Node"

# =========================
# NAME
# =========================

def rename(cfg, i, c, city):

    base = cfg.split("#")[0]
    flag = FLAGS.get(c, "🏳️")

    return f"{base}#{i} {flag} {c} | {city}"

# =========================
# PROCESS
# =========================

async def process(session, sem, cfg, i):

    async with sem:

        host, port = get_host(cfg)
        if not host:
            return None

        ms = await ping(host, port)

        # MODE FILTER
        if ms > mode["max_latency"]:
            if not mode["keep_dead"]:
                return None

        s = score(ms, cfg)
        if s <= 1 and not mode["keep_dead"]:
            return None

        c, city = await geo(session, host)

        if AUTO_RENAME:
            cfg = rename(cfg, i, c, city)

        return s, ms, cfg

# =========================
# MAIN
# =========================

async def main():

    sem = asyncio.Semaphore(THREADS)

    async with aiohttp.ClientSession() as session:

        all_cfg = []

        for url in SOURCE_SUBS:
            text = await fetch(session, url)
            text = decode(text)
            all_cfg.extend(extract(text))

        if REMOVE_DUPLICATES:
            all_cfg = list(set(all_cfg))

        tasks = [
            process(session, sem, c, i)
            for i, c in enumerate(all_cfg, 1)
        ]

        res = await asyncio.gather(*tasks)

        good = [r for r in res if r]

        # BEST FIRST
        good.sort(key=lambda x: (-x[0], x[1]))

        final = [x[2] for x in good]

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(final))

        print("MODE:", MODE)
        print("GOOD:", len(final))

# =========================
# RUN
# =========================

asyncio.run(main())
