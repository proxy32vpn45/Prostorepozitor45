import asyncio
import base64
import json
import aiohttp
import random
from urllib.parse import urlparse
import ssl
import statistics

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
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-CIDR-RU-checked.txt"
]

OUTPUT_FILE = "output.txt"
THREADS = 200
TIMEOUT = 5
REMOVE_DUPLICATES = True
AUTO_RENAME = True
SUPPORTED = ["vmess://", "vless://", "trojan://", "ss://"]

# =========================
# MODES
# =========================
MODES = {
    "strict": {"max_latency": 800, "keep_dead": True},
    "balanced": {"max_latency": 2500, "keep_dead": False},
    "relaxed": {"max_latency": 8000, "keep_dead": False},
}
MODE = "balanced"
mode = MODES[MODE]

# =========================
# FLAGS
# =========================
FLAGS = {
    "NL": "🇳🇱", "DE": "🇩🇪", "US": "🇺🇸", "FR": "🇫🇷",
    "GB": "🇬🇧", "RU": "🇷🇺", "JP": "🇯🇵", "SG": "🇸🇬",
    "CA": "🇨🇦", "TR": "🇹🇷", "PL": "🇵🇱"
}
FALLBACK = list(FLAGS.keys())

# =========================
# SCORE SYSTEM
# =========================
def score(latency, proto, tls_ok):
    if latency == 9999:
        return 0
    s = max(0, 3000 - latency)
    if tls_ok:
        s += 1000
    if proto.startswith("vless://"):
        s += 500
    elif proto.startswith("trojan://"):
        s += 400
    elif proto.startswith("vmess://"):
        s += 300
    else:
        s += 100
    return s

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
        d = base64.b64decode(text + "=" * (-len(text) % 4)).decode()
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
# MODERN PING
# =========================
async def ping(host, port, attempts=2):
    latencies = []
    for _ in range(attempts):
        try:
            loop = asyncio.get_running_loop()
            start = loop.time()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=TIMEOUT
            )
            ms = int((loop.time() - start) * 1000)
            writer.close()
            await writer.wait_closed()
            latencies.append(ms)
        except:
            pass
    if len(latencies) < 1:
        return 9999
    return int(statistics.mean(latencies))

# =========================
# TLS CHECK
# =========================
async def tls_check(host, port):
    try:
        ctx = ssl.create_default_context()
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=ctx, server_hostname=host),
            timeout=5
        )
        writer.close()
        await writer.wait_closed()
        return True
    except:
        return False

# =========================
# REAL INTERNET TEST
# =========================
async def http_test(host, port):
    try:
        url = f"https://{host}:{port}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5, ssl=False) as r:
                return r.status in [200, 400, 403]
    except:
        return False

# =========================
# GEO (CACHED)
# =========================
geo_cache = {}
async def geo(session, ip):
    if ip in geo_cache:
        return geo_cache[ip]
    try:
        async with session.get(f"https://ipwho.is/{ip}", timeout=5) as r:
            d = await r.json()
            country = d.get("country_code") or random.choice(FALLBACK)
            city = d.get("city") or "Node"
            geo_cache[ip] = (country, city)
            return country, city
    except:
        result = (random.choice(FALLBACK), "Node")
        geo_cache[ip] = result
        return result

# =========================
# RENAME
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
        if not host or not port:
            return None

        latency = await ping(host, port)
        if latency == 9999 or latency > mode["max_latency"]:
            return None

        tls_ok = await tls_check(host, port)
        if not tls_ok:
            return None

        # реальная проверка интернета
        online = await http_test(host, port)
        if not online:
            return None

        country, city = await geo(session, host)

        if AUTO_RENAME:
            cfg = rename(cfg, i, country, city)

        return score(latency, cfg, tls_ok), latency, cfg

# =========================
# MAIN
# =========================
async def main():
    sem = asyncio.Semaphore(THREADS)
    async with aiohttp.ClientSession() as session:
        all_cfg = []

        texts = await asyncio.gather(*[fetch(session, url) for url in SOURCE_SUBS])
        for text in texts:
            text = decode(text)
            all_cfg.extend(extract(text))

        if REMOVE_DUPLICATES:
            all_cfg = list(set(all_cfg))

        tasks = [process(session, sem, c, i) for i, c in enumerate(all_cfg, 1)]
        res = await asyncio.gather(*tasks)

        good = [r for r in res if r]
        good.sort(key=lambda x: (-x[0], x[1]))
        final = [x[2] for x in good]

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(final))

        print("MODE:", MODE)
        print("GOOD:", len(final))

# =========================
# RUN
# =========================
if __name__ == "__main__":
    asyncio.run(main())
