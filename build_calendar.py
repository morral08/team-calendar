#!/usr/bin/env python3
"""Build iCalendar feeds for favorite teams from ESPN's public schedule data.

Writes calendars/all.ics (every team) plus calendars/<team-key>.ics.
Standard library only. Teams are configured in teams.json.
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/teams/{id}/schedule"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "calendars")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "team-calendar-builder/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                print(f"  ! {url}: {e}", file=sys.stderr)
                return None
            time.sleep(2)


def schedule_urls(team):
    leagues = [team["league"]] + team.get("cups", [])
    urls = []
    for lg in leagues:
        u = BASE.format(sport=team["sport"], league=lg, id=team["id"])
        if team["sport"] == "soccer":
            urls += [u, u + "?fixture=true"]          # results + upcoming fixtures
        else:
            urls += [u, u + "?seasontype=3"]          # regular season + postseason
    return urls


def esc(s):
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line):
    b = line.encode("utf-8")
    if len(b) <= 75:
        return line
    parts, cur = [], b""
    for ch in line:
        cb = ch.encode("utf-8")
        if len(cur) + len(cb) > (75 if not parts else 74):
            parts.append(cur.decode("utf-8"))
            cur = b""
        cur += cb
    parts.append(cur.decode("utf-8"))
    return "\r\n ".join(parts)


def team_label(c):
    t = c.get("team", {})
    return t.get("shortDisplayName") or t.get("displayName") or t.get("name") or "TBD"


def score_of(c):
    s = c.get("score")
    if isinstance(s, dict):
        return s.get("displayValue") or s.get("value")
    return s


def broadcasts(comp):
    names = []
    for b in comp.get("broadcasts") or []:
        if isinstance(b, dict):
            n = (b.get("media") or {}).get("shortName") or b.get("shortName")
            names += b.get("names") or ([n] if n else [])
    seen = []
    for n in names:
        if n and n not in seen:
            seen.append(n)
    return seen


def to_vevent(team, ev, stamp):
    comp = (ev.get("competitions") or [{}])[0]
    competitors = comp.get("competitors") or []
    mine = next((c for c in competitors if str(c.get("id") or c.get("team", {}).get("id")) == team["id"]), None)
    other = next((c for c in competitors if c is not mine), None)
    if mine and other:
        home = mine.get("homeAway") == "home"
        summary = f"{team['name']} {'vs' if home else '@'} {team_label(other)}"
    else:
        summary = f"{team['name']}: {ev.get('shortName') or ev.get('name', 'Game')}"

    start = datetime.strptime(ev["date"].replace("Z", ""), "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc) \
        if len(ev["date"]) <= 17 else datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
    time_tbd = comp.get("timeValid") is False

    status = ((comp.get("status") or ev.get("status") or {}).get("type") or {})
    desc = []
    if status.get("completed") and mine and other:
        desc.append(f"Final: {team['name']} {score_of(mine)}, {team_label(other)} {score_of(other)}")
    elif status.get("name") in ("STATUS_POSTPONED", "STATUS_CANCELED"):
        summary += f" ({status.get('description', 'Postponed')})"
    tv = broadcasts(comp)
    if tv:
        desc.append("TV: " + ", ".join(tv))
    note = (comp.get("notes") or [{}])
    if note and note[0].get("headline"):
        desc.append(note[0]["headline"])
    if time_tbd:
        desc.append("Start time TBD")

    venue = comp.get("venue") or {}
    addr = venue.get("address") or {}
    loc = ", ".join(x for x in [venue.get("fullName"), addr.get("city"), addr.get("state") or addr.get("country")] if x)

    lines = ["BEGIN:VEVENT", f"UID:espn-{ev['id']}-{team['key']}@team-calendar", f"DTSTAMP:{stamp}"]
    if time_tbd:
        d = start.astimezone(timezone(timedelta(hours=-8))).date()  # pick the Pacific-time date
        lines += [f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}"]
    else:
        end = start + timedelta(hours=team.get("hours", 2.5))
        lines += [f"DTSTART:{start:%Y%m%dT%H%M%SZ}", f"DTEND:{end:%Y%m%dT%H%M%SZ}"]
    lines += [f"SUMMARY:{esc(summary)}", f"CATEGORIES:{esc(team['name'])}"]
    if loc:
        lines.append(f"LOCATION:{esc(loc)}")
    if desc:
        lines.append(f"DESCRIPTION:{esc(chr(10).join(desc))}")
    lines.append("END:VEVENT")
    return start, lines


def calendar(name, events):
    head = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//team-calendar//EN", "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH", f"X-WR-CALNAME:{esc(name)}", "X-WR-TIMEZONE:America/Los_Angeles",
            "REFRESH-INTERVAL;VALUE=DURATION:PT3H", "X-PUBLISHED-TTL:PT3H"]
    body = [l for _, ev in sorted(events, key=lambda e: e[0]) for l in ev]
    return "\r\n".join(fold(l) for l in head + body + ["END:VCALENDAR"]) + "\r\n"


def main():
    with open(os.path.join(HERE, "teams.json"), encoding="utf-8") as f:
        teams = json.load(f)
    os.makedirs(OUT, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    everything, failures = [], 0
    for team in teams:
        seen, events = set(), []
        for url in schedule_urls(team):
            data = fetch(url)
            for ev in (data or {}).get("events", []):
                if ev.get("id") in seen or not ev.get("date"):
                    continue
                seen.add(ev["id"])
                try:
                    events.append(to_vevent(team, ev, stamp))
                except Exception as e:  # noqa: BLE001
                    print(f"  ! skipped event {ev.get('id')}: {e}", file=sys.stderr)
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        events = [e for e in events if e[0] >= cutoff]
        print(f"{team['name']}: {len(events)} games")
        path = os.path.join(OUT, f"{team['key']}.ics")
        if events:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(calendar(team["name"], events))
        else:
            failures += 1  # keep the previous file rather than wiping the calendar
        everything += events
    if everything:
        with open(os.path.join(OUT, "all.ics"), "w", encoding="utf-8", newline="") as f:
            f.write(calendar("My Teams", everything))
    if failures == len(teams):
        sys.exit("No data fetched for any team")


if __name__ == "__main__":
    main()
