from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import pdfplumber
import requests
from bs4 import BeautifulSoup

from db import issue, replace_report_details, resolve_report_issue, upsert_match

BASE = "https://www.federhandball.it"
CALENDARS = {
    "A Gold M": "https://www.federhandball.it/campionati-nazionali/serie-a-gold/calendario-e-risultati/",
    "A1 F": "https://www.federhandball.it/campionati-nazionali/serie-a1/calendario-e-risultati/",
}
SEASON = "2026/2027"
UA = "HandballStatsResearch/1.0 (+personal non-commercial research; polite crawler)"

MONTHS = {"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,"giugno":6,"luglio":7,"agosto":8,"settembre":9,"ottobre":10,"novembre":11,"dicembre":12}


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language":"it-IT,it;q=0.9,en;q=0.6"})
    return s


def _fix_mojibake(value: str) -> str:
    """Repair common UTF-8-as-Latin-1 artefacts emitted by some FIGH PDFs."""
    if not value:
        return value
    if any(marker in value for marker in ("Ã", "Â", "â€", "â€™", "â€œ", "â€˜")):
        for source_encoding in ("cp1252", "latin-1"):
            try:
                repaired = value.encode(source_encoding).decode("utf-8")
                if repaired:
                    return repaired
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
    return value


def _norm(s: str | None) -> str:
    return _fix_mojibake(re.sub(r"\s+", " ", (s or "").strip()))


def _report_id(url: str | None) -> str | None:
    if not url: return None
    m = re.search(r"stampa_referto_pubblico/(\d+)", url)
    return m.group(1) if m else None


def discover_calendar(competition: str, url: str) -> list[dict[str, Any]]:
    """Discover matches from the official calendar page.

    The FIGH page repeats each fixture in desktop/mobile markup. We deduplicate by report id
    where present and, for scheduled games, by round/date/team tuple.
    """
    html = _session().get(url, timeout=30)
    html.raise_for_status()
    soup = BeautifulSoup(html.text, "html.parser")

    # Round markers let us tag each match while preserving postponed/advanced fixtures.
    round_nodes = []
    for node in soup.find_all(string=re.compile(r"Giornata\s+\d+\s+di\s+\d+", re.I)):
        m = re.search(r"Giornata\s+(\d+)", node, re.I)
        if m:
            round_nodes.append((node.parent, int(m.group(1))))

    anchors = [a for a in soup.find_all("a") if "Match report" in _norm(a.get_text(" ", strip=True)).lower().title() or "stampa_referto_pubblico" in (a.get("href") or "")]
    # Some not-yet-played matches have no report anchor. Add cards inferred around date strings.
    results: list[dict[str, Any]] = []
    seen = set()

    def infer_round(el) -> int | None:
        node = el.find_previous(string=re.compile(r"Giornata\s+\d+\s+di\s+\d+", re.I))
        if node:
            m = re.search(r"Giornata\s+(\d+)\s+di", str(node), re.I)
            if m:
                return int(m.group(1))
        return None

    def infer_context(el) -> str:
        # Climb until text is rich enough to contain a fixture but not an entire round/page.
        cur = el
        best = ""
        for _ in range(8):
            cur = cur.parent if cur else None
            if not cur: break
            txt = _norm(cur.get_text(" ", strip=True))
            if 30 <= len(txt) <= 700:
                best = txt
            if re.search(r"\d{1,2}\s*-\s*\d{1,2}|\bVS\b", txt, re.I) and len(txt) <= 700:
                return txt
        return best

    for a in anchors:
        href = urljoin(url, a.get("href") or "")
        rid = _report_id(href)
        context = infer_context(a)
        rno = infer_round(a)
        # Date / time
        dm = re.search(r"(?:Lunedì|Martedì|Mercoledì|Giovedì|Venerdì|Sabato|Domenica)\s+(\d{1,2})\s+([A-Za-zàèéìòù]+)\s+(20\d{2})\s*-\s*(\d{1,2})[.:](\d{2})", context, re.I)
        played_at = None
        if dm:
            month = MONTHS.get(dm.group(2).lower())
            if month:
                played_at = datetime(int(dm.group(3)), month, int(dm.group(1)), int(dm.group(4)), int(dm.group(5))).isoformat(timespec="minutes")
        score = re.search(r"\b(\d{1,2})\s*-\s*(\d{1,2})\b", context)
        # Extract likely all-caps team chunks around score. The report itself is authoritative and will overwrite names.
        team_candidates = [
            _norm(x) for x in re.findall(r"\b[A-ZÀ-ÖØ-Ý][A-ZÀ-ÖØ-Ý0-9'.` -]{3,}\b", context)
        ]
        team_candidates = [x for x in team_candidates if not re.search(r"MATCH|REPORT|SABATO|DOMENICA|LUNED|MARTED|MERCOLED|GIOVED|VENERD|GIORNATA", x)]
        home = team_candidates[0] if team_candidates else "DA VERIFICARE"
        away = team_candidates[-1] if len(team_candidates) > 1 else "DA VERIFICARE"
        match_no = int(rid) if rid else None
        key = rid or (rno, played_at, home, away)
        if key in seen: continue
        seen.add(key)
        results.append({
            "competition": competition, "season": SEASON, "round_no": rno, "match_no": match_no,
            "played_at": played_at, "venue_city": None, "venue_name": None,
            "home_team": home, "away_team": away,
            "home_goals": int(score.group(1)) if score else None,
            "away_goals": int(score.group(2)) if score else None,
            "home_ht": None, "away_ht": None,
            "status": "played" if score else "scheduled",
            "source_url": url, "report_url": href, "report_id": rid, "checksum": None,
        })
    return results


TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "intersection_tolerance": 5,
    "snap_tolerance": 4,
    "join_tolerance": 4,
}


def _extract_tables(page) -> list[list[list[str]]]:
    """Return normalized line-based tables from the report page."""
    raw_tables = page.extract_tables(TABLE_SETTINGS) or []
    return [[[_norm(c) for c in row] for row in table] for table in raw_tables]


def _extract_table_records(tables: list[list[list[str]]]) -> tuple[list[dict], list[dict]]:
    """Extract players, team officials and disciplinary events from roster tables only.

    A legitimate team table is identified structurally by the "Cognome e Nome"
    header. This is intentionally independent from the page's linear text flow,
    because pdfplumber interleaves the right-hand summary boxes with player rows
    when extracting plain text.
    """
    participants_by_key: dict[tuple, dict] = {}
    sanctions_by_key: dict[tuple, dict] = {}

    for table in tables:
        if not any(any("cognome e nome" in c.lower() for c in row) for row in table):
            continue

        side = None
        team = None
        for row in table:
            if not any(row):
                continue
            first = row[0] if row else ""

            if first in {"A", "B"} and len(row) > 1 and row[1]:
                side, team = first, _norm(row[1])
                continue
            if side is None or team is None:
                continue
            if any("cognome e nome" in c.lower() for c in row):
                continue

            name = _norm(row[1] if len(row) > 1 else "")
            if not name or not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", name):
                continue

            if re.fullmatch(r"\d{1,3}", first):
                ptype, shirt, role = "player", first, None
            elif re.fullmatch(r"UFF\.[ABCD]", first, re.I):
                ptype, shirt, role = "team_official", None, first.upper()
            else:
                continue

            goals = 0
            if ptype == "player" and len(row) > 2 and re.fullmatch(r"\d+", row[2] or ""):
                goals = int(row[2])

            pkey = (side, ptype, shirt or "", role or "", name)
            prev = participants_by_key.get(pkey)
            if prev is None:
                participants_by_key[pkey] = {
                    "side": side,
                    "team": team,
                    "person_type": ptype,
                    "shirt_no": shirt,
                    "official_role": role,
                    "name": name,
                    "goals": goals,
                }
            else:
                prev["team"] = team or prev["team"]
                prev["goals"] = max(int(prev.get("goals") or 0), goals)

            # Physical grid:
            # [N°/UFF., Nome, Reti, Amm, 2', 2', 2', Sq., San Sq.]
            # Team officials have a single meaningful 2' slot: the first one.
            labels: list[tuple[int, str, int | None]] = [
                (3, "warning", None),
                (4, "2min", 1),
            ]
            if ptype == "player":
                labels += [(5, "2min", 2), (6, "2min", 3)]
            labels += [(7, "disqualification", None), (8, "san_sq", None)]

            for idx, stype, ordinal in labels:
                if idx >= len(row) or not row[idx]:
                    continue
                vals = re.findall(r"\b\d{1,2}:\d{2}\b", row[idx]) or [_norm(row[idx])]
                for val in vals:
                    minute = val if re.fullmatch(r"\d{1,2}:\d{2}", val) else None
                    skey = (
                        side, ptype, shirt or "", role or "", name,
                        stype, minute or "", ordinal or 0, False,
                    )
                    sanctions_by_key[skey] = {
                        "side": side,
                        "team": team,
                        "person_type": ptype,
                        "shirt_no": shirt,
                        "official_role": role,
                        "person_name": name,
                        "sanction_type": stype,
                        "minute": minute,
                        "ordinal": ordinal,
                        "is_derived": False,
                        "source_column": str(idx),
                    }

            # Third player exclusion => derived DQ, kept distinct from printed Sq.
            if ptype == "player":
                third = next(
                    (
                        sx for sx in sanctions_by_key.values()
                        if sx["side"] == side
                        and sx["person_type"] == "player"
                        and sx.get("shirt_no") == shirt
                        and sx["person_name"] == name
                        and sx["sanction_type"] == "2min"
                        and sx.get("ordinal") == 3
                    ),
                    None,
                )
                if third:
                    skey = (
                        side, ptype, shirt or "", role or "", name,
                        "disqualification_3x2", third.get("minute") or "", 0, True,
                    )
                    sanctions_by_key[skey] = {
                        "side": side,
                        "team": team,
                        "person_type": ptype,
                        "shirt_no": shirt,
                        "official_role": role,
                        "person_name": name,
                        "sanction_type": "disqualification_3x2",
                        "minute": third.get("minute"),
                        "ordinal": None,
                        "is_derived": True,
                        "source_column": "derived",
                    }

    return list(participants_by_key.values()), list(sanctions_by_key.values())


def _find_pair_after_label(table: list[list[str]], label_pattern: str) -> tuple[str | None, str | None]:
    """Find the two A/B values immediately following a labelled summary row."""
    rx = re.compile(label_pattern, re.I)
    for i, row in enumerate(table):
        if any(rx.search(c or "") for c in row):
            for j in range(i + 1, min(i + 3, len(table))):
                vals = [c for c in table[j] if c]
                if len(vals) >= 2:
                    return vals[0], vals[1]
    return None, None


def _extract_report_sidebars(tables: list[list[list[str]]]) -> dict[str, Any]:
    """Parse score, half-time, 7m and assignments from their own boxed tables."""
    out: dict[str, Any] = {
        "home_goals": None, "away_goals": None,
        "home_ht": None, "away_ht": None,
        "home_7m_attempts": None, "home_7m_scored": None,
        "away_7m_attempts": None, "away_7m_scored": None,
        "assignments": [],
    }

    for table in tables:
        cells = [c for row in table for c in row if c]
        lower = [c.lower() for c in cells]

        if any("risultato" in c for c in lower):
            a, b = _find_pair_after_label(table, r"^risultato$")
            if a and b and a.isdigit() and b.isdigit():
                out["home_goals"], out["away_goals"] = int(a), int(b)
            a, b = _find_pair_after_label(table, r"^1°\s*tempo$")
            if a and b and a.isdigit() and b.isdigit():
                out["home_ht"], out["away_ht"] = int(a), int(b)

        if any("7m. tiri/reti" in c.lower() for c in cells):
            a, b = _find_pair_after_label(table, r"^7m\.\s*tiri/reti$")
            ma = re.fullmatch(r"(\d+)\s*/\s*(\d+)", a or "")
            mb = re.fullmatch(r"(\d+)\s*/\s*(\d+)", b or "")
            if ma:
                out["home_7m_attempts"], out["home_7m_scored"] = int(ma.group(1)), int(ma.group(2))
            if mb:
                out["away_7m_attempts"], out["away_7m_scored"] = int(mb.group(1)), int(mb.group(2))

        if any(re.fullmatch(r"(Arbitro|Commissario|Delegato)\s*[12]", c, re.I) for c in cells):
            labels = re.compile(r"^(Arbitro|Commissario|Delegato)\s*([12])$", re.I)
            for i, cell in enumerate(cells):
                m = labels.fullmatch(cell)
                if not m:
                    continue
                role_word = m.group(1).capitalize()
                role = f"{role_word} {m.group(2)}"
                value = None
                for nxt in cells[i + 1:]:
                    if labels.fullmatch(nxt):
                        break
                    if nxt:
                        value = _norm(nxt)
                        break
                if value:
                    out["assignments"].append({"role": role, "person_name": value})

    seen = set()
    assignments = []
    for a in out["assignments"]:
        k = (a["role"], a["person_name"])
        if k not in seen:
            seen.add(k)
            assignments.append(a)
    out["assignments"] = assignments
    return out

def parse_report(pdf_bytes: bytes, competition_hint: str | None=None, round_no: int | None=None, source_url: str | None=None) -> dict[str, Any]:
    checksum = hashlib.sha256(pdf_bytes).hexdigest()
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        page = pdf.pages[0]
        text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
        tables = _extract_tables(page)
        participants, sanctions = _extract_table_records(tables)
        sidebar = _extract_report_sidebars(tables)

    season_m = re.search(r"Stagione:\s*(\d{4}/\d{4})", text, re.I)
    head = re.search(r"Gara\s*n\.(\d+)\s*-\s*(\d{2}/\d{2}/\d{4})\s*ore\s*(\d{1,2}:\d{2})\s*-\s*Località:\s*([^\n]+)", text, re.I)
    if not head:
        raise ValueError("Intestazione del referto non riconosciuta")
    match_no = int(head.group(1))
    played_at = datetime.strptime(head.group(2)+" "+head.group(3), "%d/%m/%Y %H:%M").isoformat(timespec="minutes")
    venue_city = _norm(head.group(4))
    venue_m = re.search(r"Impianto:\s*([^\n]+)", text, re.I)

    teams = []
    for side in ("A","B"):
        pp = next((p for p in participants if p["side"]==side), None)
        if pp: teams.append((side, pp["team"]))
    team_map = dict(teams)
    home, away = team_map.get("A","DA VERIFICARE"), team_map.get("B","DA VERIFICARE")

    # Player totals are independently available from the roster. The boxed
    # "Risultato" table remains authoritative when present.
    player_home_goals = sum(
        p["goals"] for p in participants if p["side"] == "A" and p["person_type"] == "player"
    )
    player_away_goals = sum(
        p["goals"] for p in participants if p["side"] == "B" and p["person_type"] == "player"
    )
    home_goals = sidebar.get("home_goals")
    away_goals = sidebar.get("away_goals")
    if home_goals is None:
        home_goals = player_home_goals
    if away_goals is None:
        away_goals = player_away_goals

    home_ht = sidebar.get("home_ht")
    away_ht = sidebar.get("away_ht")
    home_7m_attempts = sidebar.get("home_7m_attempts")
    home_7m_scored = sidebar.get("home_7m_scored")
    away_7m_attempts = sidebar.get("away_7m_attempts")
    away_7m_scored = sidebar.get("away_7m_scored")
    assignments = sidebar.get("assignments", [])

    comp = competition_hint or ("A Gold M" if "Gold Maschile" in text else "A1 F" if "A1 Femminile" in text else "Unknown")
    return {
        "match": {
            "competition": comp, "season": season_m.group(1) if season_m else SEASON,
            "round_no": round_no, "match_no": match_no, "played_at": played_at,
            "venue_city": venue_city, "venue_name": _norm(venue_m.group(1)) if venue_m else None,
            "home_team": home, "away_team": away, "home_goals": home_goals, "away_goals": away_goals,
            "home_ht": home_ht, "away_ht": away_ht,
            "home_7m_attempts": home_7m_attempts, "home_7m_scored": home_7m_scored,
            "away_7m_attempts": away_7m_attempts, "away_7m_scored": away_7m_scored,
            "status": "played", "source_url": source_url, "report_url": source_url,
            "report_id": _report_id(source_url) or str(match_no), "checksum": checksum,
        },
        "participants": participants, "sanctions": sanctions, "assignments": assignments,
    }


def sync_all() -> dict[str, int]:
    s = _session()
    stats = {"discovered":0,"imported":0,"errors":0}
    for comp, url in CALENDARS.items():
        try:
            discovered = discover_calendar(comp, url)
        except Exception as e:
            issue(None, "calendar_fetch", f"{comp}: {e}", "error")
            stats["errors"] += 1
            continue
        for m in discovered:
            # report_id from URL is not necessarily match_no. If report exists, parse authoritative match number first.
            stats["discovered"] += 1
            if m.get("report_url"):
                try:
                    r = s.get(m["report_url"], timeout=30)
                    r.raise_for_status()
                    parsed = parse_report(r.content, comp, m.get("round_no"), m["report_url"])
                    parsed["match"]["source_url"] = url
                    mid = upsert_match(parsed["match"])
                    replace_report_details(mid, parsed["participants"], parsed["sanctions"], parsed["assignments"])
                    resolve_report_issue(m["report_url"])
                    stats["imported"] += 1
                except Exception as e:
                    # keep discovered card if it has a plausible match number, otherwise issue only
                    issue(None, "report_parse", f"{comp} {m.get('report_url')}: {e}", "error")
                    stats["errors"] += 1
            elif m.get("match_no"):
                upsert_match(m)
    return stats
