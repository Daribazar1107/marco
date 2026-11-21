"""Marco's hands: the functions the AI is allowed to call.

The AI reads each function's docstring (in English, it understands that best)
to decide which one fits the user's request. Results are returned as short
Mongolian text so the AI can repeat them to the user.
"""

import base64
from datetime import date, datetime, timedelta
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

from app.config import settings
from app.google_auth import get_service

TZ = ZoneInfo(settings.timezone)


def _to_local(value: str) -> datetime:
    """'2026-11-21T15:00' -> datetime in Ulaanbaatar time."""
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=TZ)
    return moment.astimezone(TZ)


def _message_raw(to: str, subject: str, body: str) -> str:
    message = MIMEText(body, "plain", "utf-8")
    message["to"] = to
    message["subject"] = subject
    return base64.urlsafe_b64encode(message.as_bytes()).decode()


# ---------------------------------------------------------------- Calendar


def create_calendar_event(
    title: str, start_time: str, duration_minutes: int = 60, description: str = ""
) -> str:
    """Create a new event in the user's Google Calendar.

    Args:
        title: Event title, e.g. "Meeting with teacher Amgalan"
        start_time: Start in ISO format, local time, e.g. "2026-11-21T15:00:00"
        duration_minutes: Length of the event in minutes (default 60)
        description: Optional notes for the event

    Returns:
        Confirmation text
    """
    start = _to_local(start_time)
    end = start + timedelta(minutes=int(duration_minutes or 60))
    event = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": settings.timezone},
        "end": {"dateTime": end.isoformat(), "timeZone": settings.timezone},
    }
    get_service("calendar", "v3").events().insert(calendarId="primary", body=event).execute()
    return f"Товлогдлоо: «{title}», {start:%Y-%m-%d} {start:%H:%M}-{end:%H:%M}."


def list_calendar_events(day: str, days: int = 1) -> str:
    """List the user's Google Calendar events for a day (or several days).

    Args:
        day: First day in ISO format, e.g. "2026-11-21"
        days: How many days to include, starting from day (default 1)

    Returns:
        The events, one per line
    """
    first = date.fromisoformat(day[:10])
    start = datetime.combine(first, datetime.min.time(), TZ)
    end = start + timedelta(days=max(1, int(days or 1)))
    result = (
        get_service("calendar", "v3")
        .events()
        .list(
            calendarId="primary",
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=20,
        )
        .execute()
    )
    events = result.get("items", [])
    if not events:
        return f"{first} өдрөөс хойш {days} хоногт үйл явдал алга."

    lines = []
    for event in events:
        when = event["start"].get("dateTime") or event["start"].get("date")
        if "T" in when:
            moment = _to_local(when)
            when = f"{moment:%m-%d %H:%M}"
        lines.append(f"{when} — {event.get('summary', '(нэргүй)')}")
    return "\n".join(lines)


# ---------------------------------------------------------------- Contacts


def search_contacts(name: str) -> str:
    """Find people in the user's Google Contacts by name to get their email and phone.

    Args:
        name: Name or part of a name, e.g. "Болд"

    Returns:
        Matching contacts: name | email | phone
    """
    people = get_service("people", "v1").people()
    fields = "names,emailAddresses,phoneNumbers"
    # Google asks for one empty search first to warm up its cache
    people.searchContacts(query="", readMask="names").execute()

    results = people.searchContacts(query=name, readMask=fields).execute().get("results", [])
    if not results and len(name) > 4:
        # Speech recognition may get the end of a name wrong: try the beginning only
        results = people.searchContacts(query=name[:4], readMask=fields).execute().get("results", [])
    if not results:
        return f"«{name}» нэртэй харилцагч олдсонгүй."

    lines = []
    for item in results[:5]:
        person = item["person"]
        full_name = person.get("names", [{}])[0].get("displayName", "?")
        email = person.get("emailAddresses", [{}])[0].get("value", "имэйлгүй")
        phone = person.get("phoneNumbers", [{}])[0].get("value", "утасгүй")
        lines.append(f"{full_name} | {email} | {phone}")
    return "\n".join(lines)


# ---------------------------------------------------------------- Gmail


def draft_email(to: str, subject: str, body: str) -> str:
    """Save an email as a Gmail draft. Nothing is sent.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email text

    Returns:
        Confirmation text
    """
    get_service("gmail", "v1").users().drafts().create(
        userId="me", body={"message": {"raw": _message_raw(to, subject, body)}}
    ).execute()
    return f"Gmail-д ноорог хадгаллаа: {to} руу, гарчиг «{subject}»."


def send_email(to: str, subject: str, body: str) -> str:
    """Send an email from the user's Gmail. The user must confirm first.

    Args:
        to: Recipient email address (use search_contacts if you only know the name)
        subject: Email subject
        body: Email text

    Returns:
        Confirmation text
    """
    get_service("gmail", "v1").users().messages().send(
        userId="me", body={"raw": _message_raw(to, subject, body)}
    ).execute()
    return f"Имэйл илгээгдлээ: {to} руу, гарчиг «{subject}»."


# ---------------------------------------------------------------- Registry

TOOLS = {
    tool.__name__: tool
    for tool in [
        create_calendar_event,
        list_calendar_events,
        search_contacts,
        draft_email,
        send_email,
    ]
}

# These can't be undone, so Marco asks "Илгээх үү?" before running them
NEEDS_CONFIRMATION = {"send_email"}


def describe(tool: str, args: dict) -> str:
    """Short Mongolian summary shown on the confirm card."""
    if tool == "send_email":
        return f"{args.get('to')} руу «{args.get('subject')}» гарчигтай имэйл илгээх"
    return f"{tool}({args})"
