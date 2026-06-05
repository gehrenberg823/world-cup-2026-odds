#!/usr/bin/env python3
"""Refresh the Opta Supercomputer probabilities in the WC2026 dashboard.

Pulls Stats Perform's `seasonandtournamentsimulations` feed (the same data
behind theanalyst.com's live World Cup predictions) using theanalyst's public
outlet key, derives the dashboard's six markets, and surgically rewrites only
the `opta:` numbers inside `const SEED` in index.html. The Pinnacle `market:`
values and the entry structure are left untouched.

    python3 refresh_opta.py

Markets (per Opta stage/prediction type):
    outright = P(win tournament)   Final stage, probabilityOfWinning (typeId 2)
    final    = P(reach final)      Final stage, probabilityOfQualifying (typeId 1)
    semi     = P(reach semifinal)  Semi-finals stage, typeId 1
    quarter  = P(reach quarterfinal) Quarter-finals stage, typeId 1
    advance  = P(reach Round of 32)  16th Finals stage, typeId 1
    wingroup = P(finish 1st in group) Group-stage rankDistribution rank 1 (typeId 5)
"""
from __future__ import annotations
import json, os, re, sys
from datetime import datetime
import requests

# theanalyst.com's public Opta outlet key + WC2026 tournament-calendar id
# (captured from the predictions page's performfeeds request).
OUTLET = "1mjq6w6ezkxe611ykkj8rgz7f1"
TMCL   = "873cbl9cd9butm4air0mugxzo"
FEED = (f"https://api.performfeeds.com/soccerdata/seasonandtournamentsimulations/"
        f"{OUTLET}?tmcl={TMCL}&_fmt=json&_rt=c")
HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

# Opta contestant name -> our canonical SEED team name.
NAME_MAP = {
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Congo DR": "DR Congo",
    "IR Iran": "Iran",
    "Korea Republic": "South Korea",
}
def canon(name: str) -> str:
    return NAME_MAP.get(name, name)

MARKETS = ["outright", "final", "semi", "quarter", "wingroup", "advance"]


def fetch() -> dict:
    r = requests.get(FEED, timeout=40, headers={
        "User-Agent": "Mozilla/5.0 wc2026-dashboard",
        "Referer": "https://theanalyst.com/", "Accept": "application/json"})
    r.raise_for_status()
    return json.loads(r.text, strict=False)


def _contestants(stage: dict) -> list:
    c = stage["contestants"]
    return c["contestant"] if isinstance(c, dict) else c


def _typed(predicted: list, tid: str):
    for p in predicted:
        if p.get("typeId") == tid and "value" in p:
            return float(p["value"].rstrip("%"))
    return None


def build(data: dict) -> dict:
    stages = {s["name"]: s for s in data["stages"]["stage"]}

    def stage_prob(stage_name: str, tid: str) -> dict:
        out = {}
        for c in _contestants(stages[stage_name]):
            out[canon(c["name"])] = _typed(c["predictions"][0]["predicted"], tid)
        return out

    opta = {
        "outright": stage_prob("Final", "2"),
        "final":    stage_prob("Final", "1"),
        "semi":     stage_prob("Semi-finals", "1"),
        "quarter":  stage_prob("Quarter-finals", "1"),
        "advance":  stage_prob("16th Finals", "1"),
    }
    wg = {}
    for g in stages["Group Stage"]["division"]:
        if g.get("groupName") == "3rd Place Ranking":
            continue
        for r in g["ranking"]:
            preds = r["overallPredictions"][0]["predictions"]["predicted"]
            for p in preds:
                if p.get("typeId") == "5":
                    for b in p["distribution"]:
                        if b["value"] == "1":
                            wg[canon(r["contestantName"])] = float(b["probability"].rstrip("%"))
    opta["wingroup"] = wg

    # sanity: expected coverage sums (one winner, two finalists, ... 32 advance)
    expect = {"outright": 100, "final": 200, "semi": 400, "quarter": 800,
              "wingroup": 1200, "advance": 3200}
    for m in MARKETS:
        s = sum(v for v in opta[m].values() if v is not None)
        if abs(s - expect[m]) > 1.0:
            raise SystemExit(f"sanity fail: {m} sums to {s:.1f}%, expected ~{expect[m]}%")
        print(f"  {m:9} {len(opta[m])} teams, sum {s:.1f}%")
    return opta


def num(x: float) -> str:
    return ("%.2f" % x).rstrip("0").rstrip(".") or "0"


def splice(opta: dict):
    html = open(HTML, encoding="utf-8").read()
    start = html.index("const SEED = {")
    end = html.index("\n  };", start) + len("\n  };")
    block = html[start:end]

    section = {"cur": None, "n": 0, "miss": []}
    sec_re = re.compile(r'^    (' + "|".join(MARKETS) + r'): \{')
    team_re = re.compile(r'^(?P<pre>\s*"(?P<team>[^"]+)":\s*\{ opta: )(?P<val>-?[0-9.]+)(?P<post>.*)$')

    def line_sub(line: str) -> str:
        m = sec_re.match(line)
        if m:
            section["cur"] = m.group(1)
            return line
        tm = team_re.match(line)
        if tm and section["cur"]:
            team = tm.group("team")
            v = opta.get(section["cur"], {}).get(team)
            if v is None:
                section["miss"].append((section["cur"], team))
                return line
            section["n"] += 1
            return f'{tm.group("pre")}{num(v)}{tm.group("post")}'
        return line

    new_block = "\n".join(line_sub(l) for l in block.split("\n"))
    open(HTML, "w", encoding="utf-8").write(html[:start] + new_block + html[end:])
    print(f"Updated {section['n']} opta values across {len(MARKETS)} markets.")
    if section["miss"]:
        print(f"  WARNING: {len(section['miss'])} (market,team) had no Opta value:",
              section["miss"][:10])


def stamp_marker(marker: str, value: str):
    """Rewrite the text between <!--marker--> and <!--/marker--> in index.html."""
    html = open(HTML, encoding="utf-8").read()
    new = re.sub(rf'(<!--{marker}-->).*?(<!--/{marker}-->)',
                 lambda m: m.group(1) + value + m.group(2), html, flags=re.S)
    open(HTML, "w", encoding="utf-8").write(new)


def fmt_local(iso_utc: str) -> str:
    """'2026-06-05T06:32:10Z' -> local wall-clock like '2026-06-05 01:32 CDT'."""
    dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M %Z")


if __name__ == "__main__":
    print("Fetching Opta seasonandtournamentsimulations feed...")
    data = fetch()
    last_updated = data.get("lastUpdated")
    print("  feed lastUpdated:", last_updated)
    opta = build(data)
    splice(opta)
    # Stamp the simulation's own generation time (when Opta last ran the model).
    if last_updated:
        stamp_marker("OPTA_UPDATED", fmt_local(last_updated))
