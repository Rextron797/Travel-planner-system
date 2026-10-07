from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from passlib.context import CryptContext

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from dotenv import load_dotenv
from pathlib import Path

import sqlite3
import secrets
import json
import time
import re
from contextlib import contextmanager
from fastapi.responses import JSONResponse, Response
from services.planner import compute_plan, PlanError
from services.pdf_report import build_pdf, safe_filename

from services.external_apis import (
    destination_info,
    weather,
    map_info,
    exchange,
    exchange_rate,
    status as api_status,
)


# =========================================================
# BASIC CONFIGURATION
# =========================================================

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Wanderleaf Travel Planner",
    description="Travel planning and cost estimation application",
    version="1.0.0",
)


# =========================================================
# FOLDERS
# =========================================================

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

EXPORT_DIR = BASE_DIR / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"


# =========================================================
# STATIC FILES + TEMPLATES
# =========================================================

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)

templates = Jinja2Templates(
    directory=str(TEMPLATE_DIR)
)


# =========================================================
# PASSWORD HASHING
# =========================================================

pwd = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


# =========================================================
# SESSION STORAGE
# =========================================================

# Simple in-memory sessions for the university project.
# Sessions disappear when the server restarts.
sessions = {}


# =========================================================
# DATABASE
# =========================================================

DB = DATA_DIR / "wanderleaf.db"


def conn():
    connection = sqlite3.connect(str(DB))
    connection.row_factory = sqlite3.Row
    return connection


def init():
    c = conn()

    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            currency TEXT DEFAULT 'INR'
        );

        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            destination TEXT NOT NULL,
            days INTEGER NOT NULL,
            travelers INTEGER NOT NULL,
            budget REAL DEFAULT 0,
            style TEXT,
            hotel TEXT,
            activities TEXT DEFAULT '[]',
            total REAL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (user_id)
                REFERENCES users(id)
        );
        """
    )

    c.commit()
    c.close()


init()


# =========================================================
# AUTHENTICATION HELPERS
# =========================================================

def user(request: Request):
    token = request.cookies.get("wanderleaf_session")

    if not token:
        return None

    uid = sessions.get(token)

    if not uid:
        return None

    c = conn()

    current_user = c.execute(
        "SELECT * FROM users WHERE id=?",
        (uid,),
    ).fetchone()

    c.close()

    return current_user


def context(request: Request, **kwargs):
    return {
        "request": request,
        "user": user(request),
        **kwargs,
    }


# =========================================================
# HOME
# =========================================================

@app.get("/", response_class=HTMLResponse)
def home(request: Request):

    return FileResponse(STATIC_DIR / "app.html")


# =========================================================
# DESTINATION EXPLORER
# =========================================================

@app.get("/explore", response_class=HTMLResponse)
def explore(
    request: Request,
    q: str = "Kyoto",
):

    destination = destination_info(q)

    return templates.TemplateResponse(
        "explore.html",
        context(
            request,
            name=q,
            d=destination,
            w=weather(q),
            m=map_info(q),
        ),
    )


# =========================================================
# REGISTER
# =========================================================

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):

    return templates.TemplateResponse(
        "auth.html",
        context(
            request,
            mode="register",
            error=None,
        ),
    )


@app.post("/register")
def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):

    name = name.strip()
    email = email.strip().lower()

    if not name:
        return templates.TemplateResponse(
            "auth.html",
            context(
                request,
                mode="register",
                error="Please enter your name.",
            ),
            status_code=400,
        )

    if len(password) < 6:
        return templates.TemplateResponse(
            "auth.html",
            context(
                request,
                mode="register",
                error="Use at least 6 characters for your password.",
            ),
            status_code=400,
        )

    try:
        c = conn()

        c.execute(
            """
            INSERT INTO users (
                name,
                email,
                password
            )
            VALUES (?, ?, ?)
            """,
            (
                name,
                email,
                pwd.hash(password),
            ),
        )

        c.commit()
        c.close()

    except sqlite3.IntegrityError:

        return templates.TemplateResponse(
            "auth.html",
            context(
                request,
                mode="register",
                error="That email is already registered.",
            ),
            status_code=400,
        )

    return RedirectResponse(
        "/login",
        status_code=303,
    )


# =========================================================
# LOGIN
# =========================================================

@app.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    error: int = 0,
):

    error_message = None

    if error == 1:
        error_message = "Incorrect email or password."

    return templates.TemplateResponse(
        "auth.html",
        context(
            request,
            mode="login",
            error=error_message,
        ),
    )


@app.post("/login")
def login(
    email: str = Form(...),
    password: str = Form(...),
):

    email = email.strip().lower()

    c = conn()

    u = c.execute(
        "SELECT * FROM users WHERE email=?",
        (email,),
    ).fetchone()

    c.close()

    if not u:
        return RedirectResponse(
            "/login?error=1",
            status_code=303,
        )

    try:
        valid_password = pwd.verify(
            password,
            u["password"],
        )
    except Exception:
        valid_password = False

    if not valid_password:
        return RedirectResponse(
            "/login?error=1",
            status_code=303,
        )

    token = secrets.token_urlsafe(32)

    sessions[token] = u["id"]

    response = RedirectResponse(
        "/dashboard",
        status_code=303,
    )

    response.set_cookie(
        key="wanderleaf_session",
        value=token,
        httponly=True,
        samesite="lax",
    )

    return response


# =========================================================
# LOGOUT
# =========================================================

@app.get("/logout")
def logout(request: Request):

    token = request.cookies.get(
        "wanderleaf_session"
    )

    if token:
        sessions.pop(token, None)

    response = RedirectResponse(
        "/",
        status_code=303,
    )

    response.delete_cookie(
        "wanderleaf_session"
    )

    return response


# =========================================================
# DASHBOARD
# =========================================================

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):

    u = user(request)

    if not u:
        return RedirectResponse(
            "/login",
            status_code=303,
        )

    c = conn()

    trips = c.execute(
        """
        SELECT *
        FROM trips
        WHERE user_id=?
        ORDER BY id DESC
        """,
        (u["id"],),
    ).fetchall()

    c.close()

    return templates.TemplateResponse(
        "dashboard.html",
        context(
            request,
            trips=trips,
        ),
    )


# =========================================================
# TRIP PLANNER PAGE
# =========================================================

@app.get("/plan", response_class=HTMLResponse)
def plan(
    request: Request,
    destination: str = "Kyoto",
):

    d = destination_info(destination)

    return templates.TemplateResponse(
        "plan.html",
        context(
            request,
            destination=destination,
            d=d,
        ),
    )


# =========================================================
# GENERATE TRAVEL PLAN
# =========================================================

@app.post("/plan", response_class=HTMLResponse)
def make_plan(
    request: Request,
    destination: str = Form(...),
    days: int = Form(...),
    travelers: int = Form(...),
    budget: float = Form(...),
    style: str = Form(...),
    hotel: str = Form(""),
):

    try:
        result = compute_plan(destination, days, travelers, budget, style, hotel)
    except PlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return templates.TemplateResponse(
        "result.html",
        context(
            request,
            result=result,
        ),
    )


# =========================================================
# SAVE TRIP
# =========================================================

@app.post("/save")
def save(
    request: Request,
    destination: str = Form(...),
    days: int = Form(...),
    travelers: int = Form(...),
    budget: float = Form(...),
    style: str = Form(...),
    hotel: str = Form(...),
    total: float = Form(...),
    activities: str = Form("[]"),
):

    u = user(request)

    if not u:
        return RedirectResponse(
            "/login",
            status_code=303,
        )

    # Make sure activities contains valid JSON
    try:
        parsed_activities = json.loads(
            activities
        )

        activities = json.dumps(
            parsed_activities
        )

    except json.JSONDecodeError:
        activities = "[]"

    c = conn()

    c.execute(
        """
        INSERT INTO trips (
            user_id,
            destination,
            days,
            travelers,
            budget,
            style,
            hotel,
            activities,
            total
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            u["id"],
            destination,
            days,
            travelers,
            budget,
            style,
            hotel,
            activities,
            total,
        ),
    )

    c.commit()
    c.close()

    return RedirectResponse(
        "/dashboard",
        status_code=303,
    )


# =========================================================
# DELETE SAVED TRIP
# =========================================================

@app.post("/trips/{tid}/delete")
def delete_trip(
    tid: int,
    request: Request,
):

    u = user(request)

    if not u:
        return RedirectResponse(
            "/login",
            status_code=303,
        )

    c = conn()

    c.execute(
        """
        DELETE FROM trips
        WHERE id=?
        AND user_id=?
        """,
        (
            tid,
            u["id"],
        ),
    )

    c.commit()
    c.close()

    return RedirectResponse(
        "/dashboard",
        status_code=303,
    )


# =========================================================
# TRIP COMPARISON
# =========================================================

@app.get("/compare", response_class=HTMLResponse)
def compare(
    request: Request,
    a: str = "Kyoto",
    b: str = "Goa",
):

    da = destination_info(a)
    db = destination_info(b)

    return templates.TemplateResponse(
        "compare.html",
        context(
            request,
            a=a,
            b=b,
            da=da,
            db=db,
        ),
    )


# =========================================================
# PROFILE
# =========================================================

@app.get("/profile", response_class=HTMLResponse)
def profile(request: Request):

    if not user(request):
        return RedirectResponse(
            "/login",
            status_code=303,
        )

    return templates.TemplateResponse(
        "profile.html",
        context(request),
    )


@app.post("/profile")
def update_profile(
    request: Request,
    name: str = Form(...),
    currency: str = Form(...),
):

    u = user(request)

    if not u:
        return RedirectResponse(
            "/login",
            status_code=303,
        )

    name = name.strip()

    allowed_currencies = {
        "INR",
        "USD",
        "EUR",
        "GBP",
        "JPY",
    }

    if currency not in allowed_currencies:
        currency = "INR"

    c = conn()

    c.execute(
        """
        UPDATE users
        SET name=?,
            currency=?
        WHERE id=?
        """,
        (
            name,
            currency,
            u["id"],
        ),
    )

    c.commit()
    c.close()

    return RedirectResponse(
        "/profile",
        status_code=303,
    )


# =========================================================
# PDF EXPORT
# =========================================================

@app.get("/trip/{tid}/pdf")
def pdf(tid: int, request: Request):
    u = user(request)
    if not u:
        raise HTTPException(status_code=401, detail="Login required.")
    with _db() as c:
        trip = c.execute("SELECT * FROM trips WHERE id=? AND user_id=?", (tid, u["id"])).fetchone()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found.")
    try:
        plan = compute_plan(trip["destination"], trip["days"], trip["travelers"], trip["budget"], trip["style"], trip["hotel"])
    except PlanError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _pdf_response(plan, u["name"], tid, trip["created_at"])


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "application": (
            "Wanderleaf Travel Planner"
        ),
    }

# =========================================================
# JSON API (used by static/app.html) - same DB, tables,
# sessions and cookie as the original pages.
# =========================================================

class ApiError(Exception):
    def __init__(self, msg, code=400):
        self.msg, self.code = msg, code


@app.exception_handler(ApiError)
async def _api_error(request: Request, exc: ApiError):
    return JSONResponse({"error": exc.msg}, status_code=exc.code)


@contextmanager
def _db():
    """Always commits/rolls back and closes the connection, even on errors."""
    c = conn()
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


async def _body(request: Request):
    try:
        b = await request.json()
    except Exception:
        raise ApiError("Request body must be valid JSON.")
    if not isinstance(b, dict):
        raise ApiError("Request body must be a JSON object.")
    return b


def _need_user(request: Request):
    u = user(request)
    if not u:
        raise ApiError("Please sign in.", 401)
    return u


def _plan_from(b):
    try:
        return compute_plan(b.get("destination", "Kyoto"), b.get("days", 4), b.get("travelers", 2),
                            b.get("budget", 0), b.get("style", "Mid-Range"), b.get("hotel", ""), b.get("check_in", ""))
    except PlanError as exc:
        raise ApiError(str(exc))


def _public(u):
    return {"id": u["id"], "name": u["name"], "email": u["email"], "currency": u["currency"],
            "rate": exchange_rate(u["currency"] or "INR")} if u else None


def _pdf_response(plan, user_name="", trip_id=None, created=None):
    data = build_pdf(plan, user_name=user_name, trip_id=trip_id, created=created)
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{safe_filename(plan)}"'})


@app.get("/api/status")
def api_status_route():
    """Which provider (live or demo) powers weather, maps, places, hotels and currency."""
    return api_status()


@app.get("/api/me")
def api_me(request: Request):
    return {"user": _public(user(request))}


@app.post("/api/register")
async def api_register(request: Request):
    b = await _body(request)
    name, email, password = str(b.get("name", "")).strip(), str(b.get("email", "")).strip().lower(), str(b.get("password", ""))
    if not name or len(name) > 80:
        raise ApiError("Please enter your name (up to 80 characters).")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ApiError("Please enter a valid email.")
    if len(password) < 6 or len(password.encode()) > 72:
        raise ApiError("Use 6 to 72 characters for your password.")
    try:
        with _db() as c:
            c.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, pwd.hash(password)))
    except sqlite3.IntegrityError:
        raise ApiError("That email is already registered.", 409)
    return {"ok": True}


@app.post("/api/login")
async def api_login(request: Request):
    b = await _body(request)
    with _db() as c:
        u = c.execute("SELECT * FROM users WHERE email=?", (str(b.get("email", "")).strip().lower(),)).fetchone()
    try:
        ok = bool(u) and pwd.verify(str(b.get("password", "")), u["password"])
    except Exception:
        ok = False
    if not ok:
        raise ApiError("Incorrect email or password.", 401)
    token = secrets.token_urlsafe(32)
    sessions[token] = u["id"]
    r = JSONResponse({"user": _public(u)})
    r.set_cookie("wanderleaf_session", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7)
    return r


@app.post("/api/logout")
def api_logout(request: Request):
    sessions.pop(request.cookies.get("wanderleaf_session"), None)
    r = JSONResponse({"ok": True})
    r.delete_cookie("wanderleaf_session")
    return r


@app.get("/api/destination")
def api_destination(q: str = "Kyoto"):
    """Fast: destination facts + map point (no weather call). Weather is a separate endpoint so the UI never waits on it."""
    t = time.perf_counter()
    q = q.strip()[:80] or "Kyoto"
    out = {"name": q, "d": destination_info(q), "map": map_info(q)}
    out["ms"] = round((time.perf_counter() - t) * 1000)
    return out


@app.get("/api/weather")
def api_weather(q: str = "Kyoto"):
    t = time.perf_counter()
    q = q.strip()[:80] or "Kyoto"
    return {"name": q, "weather": weather(q), "ms": round((time.perf_counter() - t) * 1000)}


@app.middleware("http")
async def _server_timing(request: Request, call_next):
    t = time.perf_counter()
    resp = await call_next(request)
    if request.url.path.startswith("/api/"):
        resp.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - t) * 1000:.0f}"
    return resp


@app.get("/api/compare")
def api_compare(a: str = "Kyoto", b: str = "Goa"):
    a, b = a.strip()[:80] or "Kyoto", b.strip()[:80] or "Goa"
    return {"a": {"name": a, "d": destination_info(a)}, "b": {"name": b, "d": destination_info(b)}}


@app.get("/api/hotels")
def api_hotels(destination: str = "Kyoto", check_in: str = "", nights: int = 1, travelers: int = 2):
    """Hotel price, location, amenities and availability (synthetic until a live provider is connected)."""
    from services.hotels import hotel_options
    destination = destination.strip()[:80] or "Kyoto"
    try:
        items = hotel_options(destination, check_in or None, nights, travelers)
    except ValueError as exc:
        raise ApiError(str(exc))
    return {"destination": destination, "check_in": check_in, "source": "synthetic-dataset", "hotels": items}


@app.post("/api/plan")
async def api_plan(request: Request):
    return _plan_from(await _body(request))


@app.post("/api/plan/pdf")          # NEW: detailed PDF of a plan before it is saved
async def api_plan_pdf(request: Request):
    u = user(request)
    return _pdf_response(_plan_from(await _body(request)), u["name"] if u else "")


@app.get("/api/trips")
def api_trips(request: Request):
    u = _need_user(request)
    with _db() as c:
        rows = c.execute("SELECT * FROM trips WHERE user_id=? ORDER BY id DESC", (u["id"],)).fetchall()
    return {"trips": [dict(r) for r in rows]}


@app.post("/api/trips")
async def api_save_trip(request: Request):
    u = _need_user(request)
    plan = _plan_from(await _body(request))          # total/itinerary are recomputed server-side, never trusted from the client
    acts = json.dumps([{"day": d["day"], "items": d["items"]} for d in plan["itinerary"]])
    with _db() as c:
        cur = c.execute(
            """INSERT INTO trips (user_id, destination, days, travelers, budget, style, hotel, activities, total)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (u["id"], plan["destination"], plan["days"], plan["travelers"], plan["budget"], plan["style"], plan["hotel"], acts, plan["total"]))
    return {"ok": True, "id": cur.lastrowid, "total": plan["total"]}


@app.delete("/api/trips/{tid}")
def api_delete_trip(tid: int, request: Request):
    u = _need_user(request)
    with _db() as c:
        gone = c.execute("DELETE FROM trips WHERE id=? AND user_id=?", (tid, u["id"])).rowcount
    if not gone:
        raise ApiError("Trip not found.", 404)
    return {"ok": True}


@app.post("/api/profile")
async def api_profile(request: Request):
    u = _need_user(request)
    b = await _body(request)
    name = str(b.get("name", "")).strip()[:80] or u["name"]
    currency = b.get("currency", "INR")
    if currency not in {"INR", "USD", "EUR", "GBP", "JPY"}:
        currency = "INR"
    with _db() as c:
        c.execute("UPDATE users SET name=?, currency=? WHERE id=?", (name, currency, u["id"]))
        row = c.execute("SELECT * FROM users WHERE id=?", (u["id"],)).fetchone()
    return {"user": _public(row)}
