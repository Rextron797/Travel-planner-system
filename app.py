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

from services.external_apis import (
    destination_info,
    weather,
    map_info,
    exchange,
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

    return templates.TemplateResponse(
        "index.html",
        context(request),
    )


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

    # Basic validation
    days = max(1, min(days, 30))
    travelers = max(1, min(travelers, 20))
    budget = max(0, budget)

    d = destination_info(destination)

    # Travel style cost multiplier
    factor = {
        "Budget": 0.75,
        "Mid-Range": 1.0,
        "Luxury": 1.65,
    }.get(style, 1.0)

    hotels = d.get("hotels", [])

    if not hotels:
        raise HTTPException(
            status_code=500,
            detail="No hotel data available.",
        )

    # Find selected hotel
    selected = next(
        (
            h
            for h in hotels
            if h[0] == hotel
        ),
        hotels[0],
    )

    # -----------------------------------------------------
    # COST CALCULATION
    # -----------------------------------------------------

    stay = round(
        selected[1]
        * days
        * factor
    )

    daily_cost = d.get("daily", 1500)

    food = round(
        daily_cost
        * 0.35
        * days
        * travelers
        * factor
    )

    transport = round(
        5000
        * factor
    )

    attraction_data = d.get(
        "attractions",
        []
    )

    activities_cost = round(
        sum(
            attraction[1]
            for attraction
            in attraction_data
        )
        * travelers
    )

    total = (
        stay
        + food
        + transport
        + activities_cost
    )

    # -----------------------------------------------------
    # ITINERARY GENERATION
    # -----------------------------------------------------

    itinerary = []

    if attraction_data:

        for i in range(days):

            first = attraction_data[
                i % len(attraction_data)
            ][0]

            second = attraction_data[
                (i + 1) % len(attraction_data)
            ][0]

            itinerary.append(
                {
                    "day": i + 1,
                    "items": [
                        first,
                        second,
                    ],
                }
            )

    # -----------------------------------------------------
    # RESULT
    # -----------------------------------------------------

    result = {
        "destination": destination,
        "days": days,
        "travelers": travelers,
        "budget": budget,
        "style": style,
        "hotel": selected[0],

        "stay": stay,
        "food": food,
        "transport": transport,
        "activities": activities_cost,

        "total": total,

        "within_budget": (
            total <= budget
            if budget > 0
            else None
        ),

        "itinerary": itinerary,

        "weather": weather(
            destination
        ),
    }

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
def pdf(
    tid: int,
    request: Request,
):

    u = user(request)

    if not u:
        raise HTTPException(
            status_code=401,
            detail="Login required.",
        )

    c = conn()

    trip = c.execute(
        """
        SELECT *
        FROM trips
        WHERE id=?
        AND user_id=?
        """,
        (
            tid,
            u["id"],
        ),
    ).fetchone()

    c.close()

    if not trip:
        raise HTTPException(
            status_code=404,
            detail="Trip not found.",
        )

    path = (
        EXPORT_DIR
        / f"trip_{tid}.pdf"
    )

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
    )

    styles = getSampleStyleSheet()

    story = [
        Paragraph(
            f"Wanderleaf - "
            f"{trip['destination']}",
            styles["Title"],
        ),

        Spacer(1, 16),

        Paragraph(
            (
                f"{trip['days']} days | "
                f"{trip['travelers']} "
                f"traveler(s) | "
                f"{trip['style']}"
            ),
            styles["BodyText"],
        ),

        Spacer(1, 8),

        Paragraph(
            f"Hotel: {trip['hotel']}",
            styles["BodyText"],
        ),

        Spacer(1, 8),

        Paragraph(
            (
                f"Budget: "
                f"INR {trip['budget']:,.0f}"
            ),
            styles["BodyText"],
        ),

        Spacer(1, 8),

        Paragraph(
            (
                f"Estimated Total: "
                f"INR {trip['total']:,.0f}"
            ),
            styles["BodyText"],
        ),

        Spacer(1, 16),

        Paragraph(
            "Estimated Cost, Not Final",
            styles["Heading3"],
        ),

        Paragraph(
            (
                "The prices shown in this travel "
                "plan are estimates and may differ "
                "from actual travel prices."
            ),
            styles["BodyText"],
        ),
    ]

    doc.build(story)

    return FileResponse(
        path=str(path),
        filename=(
            f"wanderleaf-"
            f"{trip['destination']}.pdf"
        ),
        media_type="application/pdf",
    )


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