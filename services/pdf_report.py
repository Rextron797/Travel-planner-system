"""Detailed trip-itinerary PDF (ReportLab). Returns bytes; nothing is written to disk."""
import re
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

INK, MUTE, LINE = colors.HexColor("#1e293b"), colors.HexColor("#64748b"), colors.HexColor("#e2e8f0")
TEAL, SOFT, WARN = colors.HexColor("#0f766e"), colors.HexColor("#f1f5f9"), colors.HexColor("#b45309")
inr = lambda n: f"INR {n:,.0f}"          # Helvetica has no rupee glyph
e = lambda s: escape(str(s))


def safe_filename(plan):
    slug = re.sub(r"[^A-Za-z0-9]+", "-", plan["destination"]).strip("-").lower() or "trip"
    return f"wanderleaf-{slug}-{plan['days']}-days.pdf"


def _styles():
    b = getSampleStyleSheet()["BodyText"]
    mk = lambda n, **k: ParagraphStyle(n, parent=b, textColor=k.pop("c", INK), **k)
    return {
        "title": mk("t", fontName="Helvetica-Bold", fontSize=24, leading=28, spaceAfter=2),
        "sub": mk("s", fontSize=11, c=MUTE, spaceAfter=10),
        "h": mk("h", fontName="Helvetica-Bold", fontSize=13, c=TEAL, spaceBefore=14, spaceAfter=6),
        "b": mk("b", fontSize=9.5, leading=13),
        "m": mk("m", fontSize=8.5, leading=11, c=MUTE),
        "bold": mk("bo", fontName="Helvetica-Bold", fontSize=9.5, leading=13),
        "r": mk("r", fontSize=9.5, leading=13, alignment=TA_RIGHT),
        "rb": mk("rb", fontName="Helvetica-Bold", fontSize=11, leading=14, alignment=TA_RIGHT),
    }


def _table(rows, widths, head=True, extra=()):
    t = Table(rows, colWidths=widths, repeatRows=1 if head else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
          ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
          ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]
    if head:
        st += [("BACKGROUND", (0, 0), (-1, 0), SOFT)]
    t.setStyle(TableStyle(st + list(extra)))
    return t


def build_pdf(plan, user_name="", trip_id=None, created=None):
    S, W = _styles(), A4[0] - 36 * mm
    info, wx = plan["info"], plan["weather"]
    P = lambda t, k="b": Paragraph(t, S[k])
    story = []

    # Header band + title
    band = Table([[P("<font color='white'><b>Wanderleaf</b></font>"), P("<font color='white'>Trip itinerary</font>", "r")]], colWidths=[W / 2, W / 2])
    band.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), INK), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10)]))
    story += [band, Spacer(1, 14), P(e(f"{plan['destination']} · {plan['days']} days"), "title"),
              P(e(f"{plan['travelers']} traveler(s) · {plan['style']} · {plan['hotel']}"), "sub")]

    # At a glance
    kv = lambda k, v: [P(e(k), "m"), P(e(v), "bold")]
    glance = [kv("Destination", f"{plan['destination']}, {info['country']}") + kv("Duration", f"{plan['days']} days / {plan['days']} nights"),
              kv("Travelers", plan["travelers"]) + kv("Travel style", f"{plan['style']} (x{plan['factor']})"),
              kv("Best season", info["season"]) + kv("Climate", info["climate"]),
              kv("Weather today", f"{wx['condition']}, {wx['temperature']} C ({wx['source']} data)") + kv("Map point", f"{info['lat']}, {info['lng']}"),
              kv("Stay", f"{plan['hotel']} - {plan['hotel_rating']}/5") + kv("Nightly rate", inr(plan["hotel_rate"]))]
    story += [P("Trip at a glance", "h"), _table(glance, [W * .15, W * .35, W * .15, W * .35], head=False,
              extra=[("BACKGROUND", (0, 0), (0, -1), SOFT), ("BACKGROUND", (2, 0), (2, -1), SOFT)])]

    # Cost estimate
    f, n, d = plan["factor"], plan["travelers"], plan["days"]
    rows = [[P("Item", "bold"), P("How it is estimated", "bold"), P("Amount", "rb"), P("Share", "rb")]]
    basis = {"transport": f"Flat {inr(5000)} x style factor {f}",
             "stay": f"{inr(plan['hotel_rate'])} x {d} nights x {f}",
             "food": f"{inr(plan['daily_base'])} daily base x 35% x {d} days x {n} traveler(s) x {f}",
             "activities": f"Entry fees for all {len(info['attractions'])} listed attractions x {n} traveler(s)"}
    for k in ("transport", "stay", "food", "activities"):
        rows.append([P(k.title()), P(e(basis[k]), "m"), P(inr(plan[k]), "r"), P(f"{plan['shares'][k]}%", "r")])
    rows.append([P("Total", "bold"), P(f"{inr(plan['per_person'])} per person · {inr(plan['per_day'])} per day", "m"), P(inr(plan["total"]), "rb"), P("100%", "r")])
    story += [P("Cost estimate", "h"), _table(rows, [W * .16, W * .50, W * .20, W * .14], extra=[("LINEABOVE", (0, -1), (-1, -1), 1, INK)])]
    if plan["within_budget"] is None:
        verdict = "No budget was entered."
    elif plan["within_budget"]:
        verdict = f"Within your budget of {inr(plan['budget'])} - about {inr(plan['budget_gap'])} to spare."
    else:
        verdict = f"Above your budget of {inr(plan['budget'])} by about {inr(-plan['budget_gap'])}. Try Budget style or fewer days."
    story += [Spacer(1, 6), Paragraph(f"<font color='{'#0f766e' if plan['within_budget'] is not False else '#b45309'}'><b>{e(verdict)}</b></font>", S["b"])]

    # Day by day
    story.append(P("Day-by-day itinerary", "h"))
    for day in plan["itinerary"]:
        r = [[P(f"Day {day['day']}", "bold"), "", "", ""]]
        for x in day["details"]:
            r.append([P(x["slot"], "m"), P(e(x["name"])), P(f"~{x['hours']} hr" if x["hours"] else "Flexible", "m"),
                      P(inr(x["cost"]) + " pp" if x["cost"] else "-", "r")])
        story.append(KeepTogether([_table(r, [W * .14, W * .5, W * .16, W * .2], extra=[("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ccfbf1"))]), Spacer(1, 6)]))

    # References
    ref = [[P("Attraction", "bold"), P("Time needed", "bold"), P("Entry per person", "rb")]] + [[P(e(a[0])), P(f"~{a[2]} hr", "m"), P(inr(a[1]) if a[1] else "Free", "r")] for a in info["attractions"]]
    story += [P("Attractions reference", "h"), _table(ref, [W * .5, W * .2, W * .3])]
    stays = [[P("Stay option", "bold"), P("Rating", "bold"), P("Per night", "rb")]] + [[P(e(h[0]) + (" <b>(selected)</b>" if h[0] == plan["hotel"] else "")), P(f"{h[2]}/5", "m"), P(inr(h[1]), "r")] for h in info["hotels"]]
    story += [P("Stay options", "h"), _table(stays, [W * .5, W * .2, W * .3])]

    notes = ["All prices are estimates in Indian rupees (INR) and may differ from actual travel prices.",
             "Wanderleaf is a planning tool only - it does not make bookings or take payments.",
             f"Best time to visit {plan['destination']}: {info['season']}. Check opening hours and ticket rules before you go.",
             ("Weather and map details come from demo data until live API keys are configured." if wx["source"] == "demo" else f"Weather data: {wx['source']}.")]
    story += [P("Good to know", "h")] + [P("• " + e(x)) for x in notes]

    meta = " · ".join(x for x in (f"Prepared for {user_name}" if user_name else "", f"Trip #{trip_id}" if trip_id else "", f"Saved {str(created)[:10]}" if created else "") if x)

    def footer(canvas, doc):
        canvas.saveState(); canvas.setFont("Helvetica", 8); canvas.setFillColor(MUTE)
        canvas.drawString(18 * mm, 10 * mm, f"Wanderleaf · {meta + ' · ' if meta else ''}Generated {datetime.now():%d %b %Y}")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    buf = BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                      title=f"Wanderleaf - {plan['destination']}", author="Wanderleaf").build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
