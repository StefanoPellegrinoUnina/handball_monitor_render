from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
IS_POSTGRES = DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")
DB_PATH = Path(os.getenv("HANDBALL_DB_PATH", str(BASE_DIR / "data" / "handball.sqlite3"))).expanduser()
DB_LABEL = "PostgreSQL" if IS_POSTGRES else str(DB_PATH)

if IS_POSTGRES:
    import psycopg
    from psycopg.rows import dict_row


def _sql(sql: str) -> str:
    """Translate qmark placeholders to psycopg placeholders when needed."""
    return sql.replace("?", "%s") if IS_POSTGRES else sql


@contextmanager
def connect():
    if IS_POSTGRES:
        con = psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=15)
        try:
            yield _ConnectionProxy(con)
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=5000")
        try:
            yield _ConnectionProxy(con)
            con.commit()
        finally:
            con.close()


class _ConnectionProxy:
    def __init__(self, con):
        self._con = con

    def execute(self, sql: str, params: Iterable[Any] = ()):
        return self._con.execute(_sql(sql), tuple(params))


SQLITE_SCHEMA = [
    '''CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competition TEXT NOT NULL,
        season TEXT NOT NULL,
        round_no INTEGER,
        match_no INTEGER,
        played_at TEXT,
        venue_city TEXT,
        venue_name TEXT,
        home_team TEXT NOT NULL,
        away_team TEXT NOT NULL,
        home_goals INTEGER,
        away_goals INTEGER,
        home_ht INTEGER,
        away_ht INTEGER,
        home_7m_attempts INTEGER,
        home_7m_scored INTEGER,
        away_7m_attempts INTEGER,
        away_7m_scored INTEGER,
        status TEXT NOT NULL DEFAULT 'scheduled',
        source_url TEXT,
        report_url TEXT,
        report_id TEXT,
        checksum TEXT,
        last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(competition, season, match_no)
    )''',
    '''CREATE TABLE IF NOT EXISTS participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
        side TEXT NOT NULL CHECK(side IN ('A','B')),
        team TEXT NOT NULL,
        person_type TEXT NOT NULL CHECK(person_type IN ('player','team_official')),
        shirt_no TEXT,
        official_role TEXT,
        name TEXT NOT NULL,
        goals INTEGER DEFAULT 0
    )''',
    '''CREATE TABLE IF NOT EXISTS sanctions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
        participant_id INTEGER REFERENCES participants(id) ON DELETE CASCADE,
        team TEXT NOT NULL,
        person_name TEXT,
        person_type TEXT,
        official_role TEXT,
        sanction_type TEXT NOT NULL,
        minute TEXT,
        ordinal INTEGER,
        is_derived INTEGER NOT NULL DEFAULT 0,
        source_column TEXT
    )''',
    '''CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        person_name TEXT NOT NULL,
        UNIQUE(match_id, role, person_name)
    )''',
    '''CREATE TABLE IF NOT EXISTS sync_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT DEFAULT CURRENT_TIMESTAMP,
        finished_at TEXT,
        status TEXT NOT NULL DEFAULT 'running',
        discovered INTEGER DEFAULT 0,
        imported INTEGER DEFAULT 0,
        updated INTEGER DEFAULT 0,
        errors INTEGER DEFAULT 0,
        notes TEXT
    )''',
    '''CREATE TABLE IF NOT EXISTS data_issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
        issue_type TEXT NOT NULL,
        severity TEXT NOT NULL DEFAULT 'warning',
        message TEXT NOT NULL,
        resolved INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''',
]

POSTGRES_SCHEMA = [
    '''CREATE TABLE IF NOT EXISTS matches (
        id BIGSERIAL PRIMARY KEY,
        competition TEXT NOT NULL,
        season TEXT NOT NULL,
        round_no INTEGER,
        match_no INTEGER,
        played_at TEXT,
        venue_city TEXT,
        venue_name TEXT,
        home_team TEXT NOT NULL,
        away_team TEXT NOT NULL,
        home_goals INTEGER,
        away_goals INTEGER,
        home_ht INTEGER,
        away_ht INTEGER,
        home_7m_attempts INTEGER,
        home_7m_scored INTEGER,
        away_7m_attempts INTEGER,
        away_7m_scored INTEGER,
        status TEXT NOT NULL DEFAULT 'scheduled',
        source_url TEXT,
        report_url TEXT,
        report_id TEXT,
        checksum TEXT,
        last_seen_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(competition, season, match_no)
    )''',
    '''CREATE TABLE IF NOT EXISTS participants (
        id BIGSERIAL PRIMARY KEY,
        match_id BIGINT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
        side TEXT NOT NULL CHECK(side IN ('A','B')),
        team TEXT NOT NULL,
        person_type TEXT NOT NULL CHECK(person_type IN ('player','team_official')),
        shirt_no TEXT,
        official_role TEXT,
        name TEXT NOT NULL,
        goals INTEGER DEFAULT 0
    )''',
    '''CREATE TABLE IF NOT EXISTS sanctions (
        id BIGSERIAL PRIMARY KEY,
        match_id BIGINT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
        participant_id BIGINT REFERENCES participants(id) ON DELETE CASCADE,
        team TEXT NOT NULL,
        person_name TEXT,
        person_type TEXT,
        official_role TEXT,
        sanction_type TEXT NOT NULL,
        minute TEXT,
        ordinal INTEGER,
        is_derived INTEGER NOT NULL DEFAULT 0,
        source_column TEXT
    )''',
    '''CREATE TABLE IF NOT EXISTS assignments (
        id BIGSERIAL PRIMARY KEY,
        match_id BIGINT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        person_name TEXT NOT NULL,
        UNIQUE(match_id, role, person_name)
    )''',
    '''CREATE TABLE IF NOT EXISTS sync_runs (
        id BIGSERIAL PRIMARY KEY,
        started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        finished_at TIMESTAMPTZ,
        status TEXT NOT NULL DEFAULT 'running',
        discovered INTEGER DEFAULT 0,
        imported INTEGER DEFAULT 0,
        updated INTEGER DEFAULT 0,
        errors INTEGER DEFAULT 0,
        notes TEXT
    )''',
    '''CREATE TABLE IF NOT EXISTS data_issues (
        id BIGSERIAL PRIMARY KEY,
        match_id BIGINT REFERENCES matches(id) ON DELETE CASCADE,
        issue_type TEXT NOT NULL,
        severity TEXT NOT NULL DEFAULT 'warning',
        message TEXT NOT NULL,
        resolved INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    )''',
]

INDEXES = [
    '''CREATE UNIQUE INDEX IF NOT EXISTS uq_participants
       ON participants(match_id, side, person_type, COALESCE(shirt_no,''), COALESCE(official_role,''), name)''',
    '''CREATE UNIQUE INDEX IF NOT EXISTS uq_sanctions
       ON sanctions(match_id, team, COALESCE(person_name,''), sanction_type, COALESCE(minute,''), COALESCE(ordinal,0), is_derived)''',
    '''CREATE UNIQUE INDEX IF NOT EXISTS uq_data_issues
       ON data_issues(COALESCE(match_id,0), issue_type, message)''',
]


def init_db() -> None:
    with connect() as con:
        for stmt in (POSTGRES_SCHEMA if IS_POSTGRES else SQLITE_SCHEMA):
            con.execute(stmt)
        # Non-destructive migrations for deployments created with earlier versions.
        if IS_POSTGRES:
            for col in (
                "home_7m_attempts INTEGER", "home_7m_scored INTEGER",
                "away_7m_attempts INTEGER", "away_7m_scored INTEGER",
            ):
                con.execute(f"ALTER TABLE matches ADD COLUMN IF NOT EXISTS {col}")
        else:
            existing = {r[1] for r in con.execute("PRAGMA table_info(matches)").fetchall()}
            for name in ("home_7m_attempts", "home_7m_scored", "away_7m_attempts", "away_7m_scored"):
                if name not in existing:
                    con.execute(f"ALTER TABLE matches ADD COLUMN {name} INTEGER")
        for stmt in INDEXES:
            con.execute(stmt)


def upsert_match(data: dict[str, Any]) -> int:
    cols = [
        "competition","season","round_no","match_no","played_at","venue_city","venue_name",
        "home_team","away_team","home_goals","away_goals","home_ht","away_ht",
        "home_7m_attempts","home_7m_scored","away_7m_attempts","away_7m_scored","status",
        "source_url","report_url","report_id","checksum"
    ]
    vals = [data.get(c) for c in cols]
    with connect() as con:
        cur = con.execute(f'''
        INSERT INTO matches ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})
        ON CONFLICT(competition, season, match_no) DO UPDATE SET
          round_no=excluded.round_no,
          played_at=COALESCE(excluded.played_at,matches.played_at),
          venue_city=COALESCE(excluded.venue_city,matches.venue_city),
          venue_name=COALESCE(excluded.venue_name,matches.venue_name),
          home_team=excluded.home_team,
          away_team=excluded.away_team,
          home_goals=COALESCE(excluded.home_goals,matches.home_goals),
          away_goals=COALESCE(excluded.away_goals,matches.away_goals),
          home_ht=COALESCE(excluded.home_ht,matches.home_ht),
          away_ht=COALESCE(excluded.away_ht,matches.away_ht),
          home_7m_attempts=COALESCE(excluded.home_7m_attempts,matches.home_7m_attempts),
          home_7m_scored=COALESCE(excluded.home_7m_scored,matches.home_7m_scored),
          away_7m_attempts=COALESCE(excluded.away_7m_attempts,matches.away_7m_attempts),
          away_7m_scored=COALESCE(excluded.away_7m_scored,matches.away_7m_scored),
          status=excluded.status,
          source_url=COALESCE(excluded.source_url,matches.source_url),
          report_url=COALESCE(excluded.report_url,matches.report_url),
          report_id=COALESCE(excluded.report_id,matches.report_id),
          checksum=COALESCE(excluded.checksum,matches.checksum),
          last_seen_at=CURRENT_TIMESTAMP,
          updated_at=CURRENT_TIMESTAMP
        RETURNING id
        ''', vals)
        rec = cur.fetchone()
        return int(rec["id"] if IS_POSTGRES else rec[0])


def replace_report_details(match_id: int, participants: list[dict], sanctions: list[dict], assignments: list[dict]) -> None:
    with connect() as con:
        con.execute("DELETE FROM sanctions WHERE match_id=?", (match_id,))
        con.execute("DELETE FROM participants WHERE match_id=?", (match_id,))
        con.execute("DELETE FROM assignments WHERE match_id=?", (match_id,))
        participant_ids: dict[tuple, int] = {}
        for p in participants:
            # Defensive upsert: PDF table engines can occasionally expose the same
            # roster row more than once. The logical unique key remains authoritative.
            cur = con.execute('''
                INSERT INTO participants(match_id,side,team,person_type,shirt_no,official_role,name,goals)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT DO NOTHING
                RETURNING id
            ''', (match_id,p["side"],p["team"],p["person_type"],p.get("shirt_no"),p.get("official_role"),p["name"],p.get("goals",0)))
            rec = cur.fetchone()
            key = (p["side"],p["person_type"],p.get("shirt_no") or "",p.get("official_role") or "",p["name"])
            if rec:
                pid = int(rec["id"] if IS_POSTGRES else rec[0])
            else:
                found = con.execute('''
                    SELECT id FROM participants
                    WHERE match_id=? AND side=? AND person_type=?
                      AND COALESCE(shirt_no,'')=? AND COALESCE(official_role,'')=? AND name=?
                ''', (match_id, p["side"], p["person_type"], p.get("shirt_no") or "", p.get("official_role") or "", p["name"])).fetchone()
                pid = int(found["id"] if IS_POSTGRES else found[0])
                con.execute("UPDATE participants SET team=?, goals=? WHERE id=?", (p["team"], p.get("goals",0), pid))
            participant_ids[key] = pid
        for s in sanctions:
            key = (s.get("side"),s.get("person_type"),s.get("shirt_no") or "",s.get("official_role") or "",s.get("person_name") or "")
            pid = participant_ids.get(key)
            con.execute('''
                INSERT INTO sanctions(match_id,participant_id,team,person_name,person_type,official_role,sanction_type,minute,ordinal,is_derived,source_column)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT DO NOTHING
            ''', (match_id,pid,s["team"],s.get("person_name"),s.get("person_type"),s.get("official_role"),s["sanction_type"],s.get("minute"),s.get("ordinal"),1 if s.get("is_derived") else 0,s.get("source_column")))
        for a in assignments:
            con.execute("INSERT INTO assignments(match_id,role,person_name) VALUES(?,?,?) ON CONFLICT DO NOTHING", (match_id,a["role"],a["person_name"]))


def rows(sql: str, params: Iterable[Any]=()) -> list[dict[str, Any]]:
    with connect() as con:
        cur = con.execute(sql, params)
        fetched = cur.fetchall()
        return [dict(r) for r in fetched]


def row(sql: str, params: Iterable[Any]=()) -> dict[str, Any] | None:
    with connect() as con:
        r = con.execute(sql, params).fetchone()
        return dict(r) if r else None


def issue(match_id: int | None, issue_type: str, message: str, severity: str="warning") -> None:
    with connect() as con:
        con.execute(
            "INSERT INTO data_issues(match_id,issue_type,severity,message) VALUES(?,?,?,?) ON CONFLICT DO NOTHING",
            (match_id, issue_type, severity, message)
        )


def resolve_report_issue(source_url: str) -> None:
    """Resolve stale parse errors for a report after a later successful import."""
    if not source_url:
        return
    with connect() as con:
        con.execute(
            "UPDATE data_issues SET resolved=1 WHERE issue_type='report_parse' AND resolved=0 AND message LIKE ?",
            (f"%{source_url}%",),
        )
