from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import threading
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from db import DB_LABEL, DATABASE_URL, connect, init_db, replace_report_details, row, rows, upsert_match
from scraper import parse_report, sync_all

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Handball Monitor Italia", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

_scheduler_stop = threading.Event()
_scheduler_thread = None
_sync_lock = threading.Lock()


def run_sync_job():
    # Prevent a manual sync and the scheduled sync from writing simultaneously.
    if not _sync_lock.acquire(blocking=False):
        return {"status": "busy", "discovered": 0, "imported": 0, "errors": 0}
    try:
        with connect() as con:
            cur = con.execute("INSERT INTO sync_runs(status) VALUES('running') RETURNING id")
            rec = cur.fetchone()
            run_id = int(rec["id"] if hasattr(rec, "keys") else rec[0])
        try:
            st = sync_all()
            final_status = "ok" if st.get("errors", 0) == 0 else "partial"
            with connect() as con:
                con.execute(
                    "UPDATE sync_runs SET finished_at=CURRENT_TIMESTAMP,status=?,discovered=?,imported=?,errors=? WHERE id=?",
                    (final_status, st['discovered'], st['imported'], st['errors'], run_id),
                )
            return {"status": final_status, **st}
        except Exception as e:
            with connect() as con:
                con.execute(
                    "UPDATE sync_runs SET finished_at=CURRENT_TIMESTAMP,status='error',errors=1,notes=? WHERE id=?",
                    (str(e), run_id),
                )
            return {"status": "error", "discovered": 0, "imported": 0, "errors": 1, "notes": str(e)}
    finally:
        _sync_lock.release()


def _scheduler_targets():
    raw = os.getenv("SYNC_TIMES", "23:10,07:15")
    targets = set()
    for item in raw.split(","):
        try:
            hh, mm = item.strip().split(":", 1)
            targets.add((int(hh), int(mm)))
        except Exception:
            continue
    return targets or {(23, 10), (7, 15)}


def _scheduler_days():
    # 0=Monday ... 6=Sunday. "*" means every day.
    raw = os.getenv("SYNC_DAYS", "*").strip()
    if raw == "*":
        return set(range(7))
    out = set()
    for x in raw.split(","):
        try:
            n = int(x.strip())
            if 0 <= n <= 6:
                out.add(n)
        except Exception:
            pass
    return out or set(range(7))


def _scheduler_loop():
    tz = ZoneInfo(os.getenv("APP_TIMEZONE", "Europe/Rome"))
    last_key = None
    targets = _scheduler_targets()
    days = _scheduler_days()
    while not _scheduler_stop.wait(20):
        now = datetime.now(tz)
        key = (now.date().isoformat(), now.hour, now.minute)
        if now.weekday() in days and (now.hour, now.minute) in targets and key != last_key:
            last_key = key
            run_sync_job()


def _initial_sync_if_empty():
    # First deployment starts with an empty persistent disk. Populate it without
    # blocking the HTTP startup path. Subsequent deploys keep the existing DB.
    try:
        count = row("SELECT COUNT(*) n FROM matches") or {"n": 0}
        if int(count.get("n", 0)) == 0 and os.getenv("AUTO_SYNC_ON_EMPTY_DB", "1") == "1":
            _scheduler_stop.wait(3)
            if not _scheduler_stop.is_set():
                run_sync_job()
    except Exception:
        pass


@app.on_event("startup")
def startup():
    global _scheduler_thread
    if os.getenv("RENDER") == "true" and not DATABASE_URL:
        raise RuntimeError("DATABASE_URL non configurato: collega prima il database PostgreSQL esterno.")
    init_db()
    _scheduler_stop.clear()
    threading.Thread(target=_initial_sync_if_empty, name="figh-first-sync", daemon=True).start()
    if os.getenv("DISABLE_SCHEDULER", "0") != "1":
        _scheduler_thread = threading.Thread(target=_scheduler_loop, name="figh-sync", daemon=True)
        _scheduler_thread.start()


@app.on_event("shutdown")
def shutdown():
    _scheduler_stop.set()


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request":request})


@app.get("/healthz")
def healthz():
    check = row("SELECT COUNT(*) n FROM matches") or {"n": 0}
    return {"ok": True, "database": DB_LABEL, "matches": check.get("n", 0)}


def comp_filter(comp: str | None):
    return (" AND competition=?", [comp]) if comp and comp != "ALL" else ("", [])


@app.get("/api/overview")
def overview(competition: str = "ALL"):
    w,p = comp_filter(competition)
    totals = row(f'''SELECT
        COUNT(*) games,
        SUM(CASE WHEN status='played' THEN 1 ELSE 0 END) played,
        COALESCE(SUM(home_goals+away_goals),0) goals
        FROM matches WHERE 1=1 {w}''', p) or {}
    sanc = row(f'''SELECT
        SUM(CASE WHEN sanction_type='2min' THEN 1 ELSE 0 END) two_min,
        SUM(CASE WHEN sanction_type IN ('disqualification','disqualification_3x2') THEN 1 ELSE 0 END) dq,
        SUM(CASE WHEN person_type='team_official' THEN 1 ELSE 0 END) bench
        FROM sanctions s JOIN matches m ON m.id=s.match_id WHERE s.is_derived=0 {w}''', p) or {}
    issues = row("SELECT COUNT(*) n FROM data_issues WHERE resolved=0") or {"n":0}
    last = row("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1")
    return {**totals, **sanc, "issues":issues.get("n",0), "last_sync":last}


@app.get("/api/matches")
def matches(competition: str="ALL", round_no: int|None=None):
    sql="SELECT m.* FROM matches m WHERE 1=1"
    params=[]
    if competition!="ALL": sql+=" AND competition=?"; params.append(competition)
    if round_no is not None: sql+=" AND round_no=?"; params.append(round_no)
    sql+=" ORDER BY COALESCE(played_at,'9999'), competition, round_no, match_no"
    data = rows(sql,params)
    if not data:
        return data
    aids = rows("SELECT match_id, role, person_name FROM assignments ORDER BY match_id, role, person_name")
    by_match = {}
    for a in aids:
        bucket = by_match.setdefault(a["match_id"], {"referees": [], "delegates": []})
        if str(a["role"]).lower().startswith("arbitro"):
            bucket["referees"].append(a["person_name"])
        elif str(a["role"]).lower().startswith("commissario") or str(a["role"]).lower().startswith("delegato"):
            bucket["delegates"].append(a["person_name"])
    for m in data:
        bucket = by_match.get(m["id"], {"referees": [], "delegates": []})
        m["referees"] = " / ".join(bucket["referees"]) or None
        m["delegates"] = " / ".join(bucket["delegates"]) or None
    return data


@app.get("/api/team-stats")
def team_stats(competition: str="ALL"):
    where=""; params=[]
    if competition!="ALL": where=" WHERE m.competition=?"; params=[competition]
    sql=f'''
    WITH tg AS (
      SELECT m.id,m.competition,m.home_team team,m.home_goals gf,m.away_goals ga FROM matches m WHERE m.status='played'
      UNION ALL
      SELECT m.id,m.competition,m.away_team,m.away_goals,m.home_goals FROM matches m WHERE m.status='played'
    ), sx AS (
      SELECT s.match_id,s.team,
        SUM(CASE WHEN s.sanction_type='2min' AND s.is_derived=0 THEN 1 ELSE 0 END) two_min,
        SUM(CASE WHEN s.sanction_type='disqualification' AND s.is_derived=0 THEN 1 ELSE 0 END) direct_dq,
        SUM(CASE WHEN s.person_type='team_official' AND s.is_derived=0 THEN 1 ELSE 0 END) bench_sanctions
      FROM sanctions s GROUP BY s.match_id,s.team
    )
    SELECT tg.team, tg.competition, COUNT(*) games, SUM(gf) gf, SUM(ga) ga,
           ROUND(AVG(gf),2) avg_gf, COALESCE(SUM(sx.two_min),0) two_min,
           COALESCE(SUM(sx.direct_dq),0) direct_dq, COALESCE(SUM(sx.bench_sanctions),0) bench_sanctions
    FROM tg JOIN matches m ON m.id=tg.id LEFT JOIN sx ON sx.match_id=tg.id AND sx.team=tg.team
    {where}
    GROUP BY tg.team,tg.competition ORDER BY tg.competition,tg.team
    '''
    return rows(sql,params)


@app.get("/api/players")
def players(competition: str="ALL", q: str=""):
    sql = """
      WITH pg AS (
        SELECT p.id,p.name,p.team,p.match_id,p.goals,m.competition
        FROM participants p JOIN matches m ON m.id=p.match_id
        WHERE p.person_type='player'
      ), sx AS (
        SELECT participant_id,
          SUM(CASE WHEN sanction_type='2min' AND is_derived=0 THEN 1 ELSE 0 END) two_min,
          SUM(CASE WHEN sanction_type='disqualification' AND is_derived=0 THEN 1 ELSE 0 END) direct_dq,
          SUM(CASE WHEN sanction_type='disqualification_3x2' THEN 1 ELSE 0 END) dq_3x2
        FROM sanctions GROUP BY participant_id
      )
      SELECT pg.name,pg.team,pg.competition,COUNT(DISTINCT pg.match_id) games,SUM(pg.goals) goals,
             COALESCE(SUM(sx.two_min),0) two_min,COALESCE(SUM(sx.direct_dq),0) direct_dq,
             COALESCE(SUM(sx.dq_3x2),0) dq_3x2
      FROM pg LEFT JOIN sx ON sx.participant_id=pg.id WHERE 1=1
    """
    params=[]
    if competition!="ALL": sql+=" AND pg.competition=?"; params.append(competition)
    if q: sql+=" AND pg.name LIKE ?"; params.append(f"%{q}%")
    sql+=" GROUP BY pg.name,pg.team,pg.competition ORDER BY goals DESC,pg.name"
    return rows(sql,params)


@app.get("/api/sanctions")
def sanctions(competition: str="ALL", bench_only: bool=False):
    sql='''SELECT s.*,m.competition,m.round_no,m.played_at,m.home_team,m.away_team,m.report_url
      FROM sanctions s JOIN matches m ON m.id=s.match_id WHERE s.is_derived=0'''
    params=[]
    if competition!="ALL": sql+=" AND m.competition=?"; params.append(competition)
    if bench_only: sql+=" AND s.person_type='team_official'"
    sql+=" ORDER BY m.played_at DESC,s.team,s.person_name,s.minute"
    return rows(sql,params)


@app.get("/api/assignments")
def assignments(competition: str="ALL"):
    sql='''SELECT a.person_name,a.role,m.competition,m.round_no,m.played_at,m.home_team,m.away_team,m.report_url
      FROM assignments a JOIN matches m ON m.id=a.match_id WHERE 1=1'''
    params=[]
    if competition!="ALL": sql+=" AND m.competition=?"; params.append(competition)
    sql+=" ORDER BY m.played_at DESC,a.role,a.person_name"
    return rows(sql,params)


@app.get("/api/pairs")
def referee_pairs(competition: str="ALL"):
    sql='''SELECT m.id,m.competition,m.round_no,m.played_at,m.home_team,m.away_team,
      MAX(CASE WHEN a.role='Arbitro 1' THEN a.person_name END) r1,
      MAX(CASE WHEN a.role='Arbitro 2' THEN a.person_name END) r2,
      MAX(CASE WHEN a.role='Commissario 1' THEN a.person_name END) d1,
      MAX(CASE WHEN a.role='Commissario 2' THEN a.person_name END) d2,
      m.report_url
      FROM matches m LEFT JOIN assignments a ON a.match_id=m.id WHERE m.status='played' '''
    params=[]
    if competition!="ALL": sql+=" AND m.competition=?"; params.append(competition)
    sql+=" GROUP BY m.id ORDER BY m.played_at DESC"
    return rows(sql,params)


@app.get("/api/issues")
def issues():
    return rows('''SELECT d.*,m.competition,m.round_no,m.home_team,m.away_team FROM data_issues d
      LEFT JOIN matches m ON m.id=d.match_id WHERE d.resolved=0 ORDER BY d.created_at DESC''')


@app.post("/api/sync")
def sync():
    result = run_sync_job()
    if result.get("status") == "busy":
        raise HTTPException(409, "Una sincronizzazione è già in corso")
    return {"ok": result.get("status") in {"ok", "partial"}, "result": result, "last": row("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1")}


@app.post("/api/sync-scheduled")
def sync_scheduled(request: Request, force: bool=False):
    expected = os.getenv("SYNC_TOKEN", "").strip()
    supplied = request.headers.get("X-Sync-Token", "")
    if not expected or supplied != expected:
        raise HTTPException(401, "Token di sincronizzazione non valido")

    # GitHub Actions uses two UTC slots around each Europe/Rome target to survive DST.
    # Only the invocation that lands in an allowed local hour actually performs the sync.
    if not force:
        tz = ZoneInfo(os.getenv("APP_TIMEZONE", "Europe/Rome"))
        now = datetime.now(tz)
        allowed = {int(x.strip()) for x in os.getenv("SCHEDULE_HOURS", "7,23").split(",") if x.strip().isdigit()}
        if now.hour not in allowed:
            return {"ok": True, "skipped": True, "local_time": now.isoformat(timespec="minutes")}

    result = run_sync_job()
    if result.get("status") == "busy":
        raise HTTPException(409, "Una sincronizzazione è già in corso")
    return {"ok": result.get("status") in {"ok", "partial"}, "result": result}


@app.post("/api/import-report")
async def import_report(file: UploadFile = File(...), competition: str="A Gold M", round_no: int|None=None):
    body=await file.read()
    parsed=parse_report(body, competition, round_no, None)
    mid=upsert_match(parsed["match"])
    replace_report_details(mid, parsed["participants"], parsed["sanctions"], parsed["assignments"])
    return {"ok":True,"match_id":mid,"match":parsed["match"]}


@app.post("/api/import-json")
async def import_json(request: Request):
    data=await request.json()
    if not isinstance(data, dict) or "match" not in data:
        raise HTTPException(400,"JSON non valido: richiesto oggetto con chiave match")
    mid=upsert_match(data["match"])
    replace_report_details(mid,data.get("participants",[]),data.get("sanctions",[]),data.get("assignments",[]))
    return {"ok":True,"match_id":mid}


@app.get("/api/export-json")
def export_json():
    payload = {
        "generated_at": datetime.now(ZoneInfo(os.getenv("APP_TIMEZONE", "Europe/Rome"))).isoformat(timespec="seconds"),
        "database_version": 1,
        "matches": rows("SELECT * FROM matches ORDER BY competition, round_no, match_no"),
        "participants": rows("SELECT * FROM participants ORDER BY match_id, side, person_type, shirt_no, official_role, name"),
        "sanctions": rows("SELECT * FROM sanctions ORDER BY match_id, team, person_name, minute"),
        "assignments": rows("SELECT * FROM assignments ORDER BY match_id, role, person_name"),
        "data_issues": rows("SELECT * FROM data_issues ORDER BY created_at"),
        "sync_runs": rows("SELECT * FROM sync_runs ORDER BY id"),
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return JSONResponse(
        content=jsonable_encoder(payload),
        headers={"Content-Disposition": f'attachment; filename="handball_monitor_backup_{stamp}.json"'},
    )
