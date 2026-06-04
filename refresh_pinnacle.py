#!/usr/bin/env python3
"""Refresh the Pinnacle ("market") de-vigged probabilities in the WC2026 dashboard.

Pulls Pinnacle's public guest API for the FIFA World Cup league (2686), de-vigs
each of the dashboard's six markets, and surgically rewrites the `market:` value
of each team in `const SEED` (leaving the Opta values and structure untouched).

De-vig (matches the original SEED methodology):
  * Two-way markets (reach final/semi/quarter, qualify-from-group) -> Yes vs No.
  * Field markets (outright winner, group winner)                 -> normalize
    implied probability across the whole field.

Usage:
    python3 refresh_pinnacle.py            # verify only: print old-vs-new, no write
    python3 refresh_pinnacle.py --write    # also splice into index.html
"""
from __future__ import annotations
import json, os, re, sys
import requests

KEY = "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R"   # Pinnacle public guest x-api-key
LEAGUE = 2686                              # FIFA - World Cup
BASE = "https://guest.api.arcadia.pinnacle.com/0.1"
HDR = {"x-api-key": KEY, "User-Agent": "Mozilla/5.0", "Accept": "application/json"}
HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
MARKETS = ["outright", "final", "semi", "quarter", "wingroup", "advance"]

# Pinnacle name -> our canonical SEED team name.
NAME_MAP = {
    "USA": "United States", "Turkiye": "Türkiye", "Ivory Coast": "Côte d'Ivoire",
    "Cape Verde": "Cabo Verde", "Curacao": "Curaçao", "Congo DR": "DR Congo",
    "Korea Republic": "South Korea", "IR Iran": "Iran",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
}
def canon(n: str) -> str:
    return NAME_MAP.get(n, n)


def implied(american: float) -> float:
    return (-american) / (-american + 100.0) if american < 0 else 100.0 / (american + 100.0)


def fetch():
    mu = requests.get(f"{BASE}/leagues/{LEAGUE}/matchups", headers=HDR,
                      params={"brandId": 0}, timeout=40).json()
    straight = requests.get(f"{BASE}/leagues/{LEAGUE}/markets/straight", headers=HDR,
                            timeout=60).json()
    prices = {}   # matchupId -> {participantId: american}
    for mk in straight:
        if mk.get("key") == "s;0;m":   # straight, period 0, moneyline
            prices[mk["matchupId"]] = {p["participantId"]: p["price"]
                                       for p in mk.get("prices", []) if "participantId" in p}
    return mu, prices


def team_of(desc: str) -> str:
    return canon(desc.split(" To ")[0].strip())


def build(mu, prices) -> dict:
    out = {m: {} for m in MARKETS}

    def two_way(m, team, mid):
        pr = prices.get(mid) or {}
        parts = {p["name"]: p["id"] for p in byid[mid]["participants"]}
        yp, npid = parts.get("Yes"), parts.get("No")
        ay, an = pr.get(yp), pr.get(npid)
        if ay is None or an is None:
            return
        iy, ino = implied(ay), implied(an)
        out[m][team] = round(100.0 * iy / (iy + ino), 2)

    def field(target, mid):
        pr = prices.get(mid) or {}
        imps = {}
        for p in byid[mid]["participants"]:
            a = pr.get(p["id"])
            if a is not None:
                imps[p["name"]] = implied(a)
        tot = sum(imps.values())
        if tot <= 0:
            return
        for name, im in imps.items():
            target[canon(name)] = round(100.0 * im / tot, 2)

    byid = {m["id"]: m for m in mu}
    for m in mu:
        sp = m.get("special") or {}
        cat, desc, units = sp.get("category"), sp.get("description") or "", m.get("units")
        if cat == "Futures" and "Winner" in desc:
            field(out["outright"], m["id"])
        elif cat == "To Reach The Final":
            two_way("final", team_of(desc), m["id"])
        elif cat == "To Reach Semi Final":
            two_way("semi", team_of(desc), m["id"])
        elif cat == "To Reach Quarter Final":
            two_way("quarter", team_of(desc), m["id"])
        elif units == "To Qualify":
            two_way("advance", team_of(desc), m["id"])
        elif units == "Place 1st" and re.match(r"Group [A-L] Winner$", desc):
            field(out["wingroup"], m["id"])
    for m in MARKETS:
        print(f"  {m:9} {len(out[m])} teams priced")
    return out


def load_seed_market():
    """Current SEED market values per (section, team) for comparison."""
    html = open(HTML, encoding="utf-8").read()
    block = html[html.index("const SEED = {"):html.index("\n  };", html.index("const SEED = {"))]
    cur, vals = None, {}
    for line in block.split("\n"):
        ms = re.match(r"^    (" + "|".join(MARKETS) + r"): \{", line)
        if ms:
            cur = ms.group(1); continue
        mt = re.match(r'^\s*"([^"]+)":\s*\{ opta: [-0-9.]+(?:, market: ([-0-9.]+))? \}', line)
        if mt and cur:
            vals[(cur, mt.group(1))] = float(mt.group(2)) if mt.group(2) else None
    return vals


def verify(new, old):
    print("\n=== old (SEED) vs new (live Pinnacle) — sample + drift ===")
    for m in MARKETS:
        teams = sorted(new[m], key=lambda t: -new[m][t])[:6]
        print(f"-- {m} --")
        big = 0
        for (sec, t), ov in old.items():
            if sec == m and t in new[m] and ov is not None and abs(new[m][t] - ov) > 3.0:
                big += 1
        for t in teams:
            ov = old.get((m, t))
            print(f"   {t:24} old={ov if ov is not None else '—':>7}  new={new[m][t]:>6}")
        print(f"   (>3pt moves vs yesterday: {big})")


def splice(new):
    html = open(HTML, encoding="utf-8").read()
    s = html.index("const SEED = {"); e = html.index("\n  };", s) + len("\n  };")
    block = html[s:e]
    cur = {"sec": None, "set": 0, "add": 0}
    sec_re = re.compile(r"^    (" + "|".join(MARKETS) + r"): \{")
    row_re = re.compile(r'^(?P<pre>\s*"(?P<team>[^"]+)":\s*\{ opta: (?P<opta>[-0-9.]+))(?P<mid>(?:, market: [-0-9.]+)?)(?P<post> \}.*)$')

    def fmt(v):
        return ("%.2f" % v).rstrip("0").rstrip(".") or "0"

    def sub(line):
        ms = sec_re.match(line)
        if ms:
            cur["sec"] = ms.group(1); return line
        mr = row_re.match(line)
        if mr and cur["sec"]:
            v = new[cur["sec"]].get(mr.group("team"))
            if v is None:
                return line   # Pinnacle doesn't price this team/market now: leave as-is
            had = bool(mr.group("mid"))
            cur["set" if had else "add"] += 1
            return f'{mr.group("pre")}, market: {fmt(v)}{mr.group("post")}'
        return line

    new_block = "\n".join(sub(l) for l in block.split("\n"))
    open(HTML, "w", encoding="utf-8").write(html[:s] + new_block + html[e:])
    print(f"\nWrote market values: {cur['set']} updated, {cur['add']} newly added.")


if __name__ == "__main__":
    print("Fetching Pinnacle WC2026 guest-API matchups + prices...")
    mu, prices = fetch()
    new = build(mu, prices)
    old = load_seed_market()
    verify(new, old)
    # report unmatched team names (priced by Pinnacle but not in SEED)
    seed_teams = {t for (_, t) in old}
    unmatched = sorted({t for m in MARKETS for t in new[m]} - seed_teams)
    if unmatched:
        print("\nUNMATCHED Pinnacle names (need NAME_MAP entry):", unmatched)
    if "--write" in sys.argv:
        splice(new)
    else:
        print("\n(verify only — rerun with --write to update index.html)")
