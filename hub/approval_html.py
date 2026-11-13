"""Human-readable approval pages; protocol IDs and preconditions stay server-side."""
from datetime import date, datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo


def _when(value):
    if isinstance(value, dict):
        value = value.get("dateTime") or value.get("date") or ""
    value = str(value or "")
    try:
        if len(value) == 10:
            return date.fromisoformat(value).strftime("%A, %B %-d, %Y") + " (all day)"
        return datetime.fromisoformat(value).astimezone(ZoneInfo("America/Vancouver")).strftime("%a, %b %-d at %-I:%M %p %Z")
    except ValueError:
        return value[:300]


def _event(title, start, end, location=""):
    text = f"<p><strong>{escape(str(title or 'Untitled event'))}</strong></p>"
    first = start.get("date") if isinstance(start, dict) else start
    last = end.get("date") if isinstance(end, dict) else end
    try:
        first_day, last_day = date.fromisoformat(first), date.fromisoformat(last) - timedelta(days=1)
        period = _when(first_day.isoformat())
        if last_day != first_day:
            period += " through " + _when(last_day.isoformat())
    except (ValueError, TypeError):
        period = _when(start) + " — " + _when(end)
    text += f"<p>{escape(period)}</p>"
    if location:
        text += f"<p>{escape(str(location)[:500])}</p>"
    return text


def page(body):
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Catthew calendar approval</title><style>body{font:18px/1.5 system-ui,sans-serif;margin:2rem auto;padding:0 1rem;max-width:40rem;color:#171717}h1{line-height:1.2}button{font:inherit;min-height:44px;padding:.6rem 1rem;margin:.5rem .5rem .5rem 0;border:2px solid #222;background:white;color:#171717}button[value=allow]{background:#842323;color:white;border-color:#842323}button:disabled{opacity:.5}p{overflow-wrap:anywhere}</style><main>' + body + '</main></html>')


def shell_page():
    return page('<h1>Catthew calendar approval</h1><p>Loading your private approval…</p><noscript>JavaScript is required to open this private link.</noscript><script src="/approval/client.js" defer></script>')


def message_page(message):
    return page("<h1>Catthew calendar approval</h1><p>" + escape(message) + "</p>")


def proposal_page(record):
    current, proposed = record["preview"], record["payload"]
    body = '<h1>Review calendar change</h1><p>The calendar has not been changed. This link can be used once.</p><h2>Current event</h2>'
    body += _event(current.get("summary"), current.get("start"), current.get("end"), current.get("location"))
    body += '<h2>Proposed change</h2>'
    if record["kind"] == "delete":
        body += '<p>Delete this event from Kittyggup Family.</p>'
    else:
        body += _event(proposed.get("title"), proposed.get("start"), proposed.get("end"))
    body += ('<form method="post"><button name="decision" value="allow">Approve this change</button> '
             '<button name="decision" value="deny">Deny</button></form>')
    return page(body)
