"""Google Calendar operations permanently bound to the configured family calendar."""
from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import date, datetime


class CalendarConflict(ValueError):
    pass


def _time(value):
    if not isinstance(value, str):
        raise ValueError("calendar time must be text")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        date.fromisoformat(value)
        return {"date": value}
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("calendar time requires a timezone")
    return {"dateTime": value, "timeZone": "America/Vancouver"}


def event_interval(start, end):
    """Validate one all-day or timezone-aware interval before proposing/writing."""
    begin, finish = _time(start), _time(end)
    if ("date" in begin) != ("date" in finish):
        raise ValueError("event time types must match")
    if (date.fromisoformat(end) <= date.fromisoformat(start) if "date" in begin
            else datetime.fromisoformat(end) <= datetime.fromisoformat(start)):
        raise ValueError("event end must follow start")
    return begin, finish


def _etag(value):
    if not isinstance(value, str) or not re.fullmatch(r'"[^"\r\n]+"', value):
        raise ValueError("a single concrete event etag is required")
    return value


class FamilyCalendar:
    def __init__(self, calendar_id, service):
        if not isinstance(calendar_id, str) or not calendar_id or calendar_id == "primary":
            raise ValueError("an explicit family calendar ID is required")
        self.calendar_id = calendar_id
        self.service = service
        self.lock = threading.RLock()

    def _execute(self, request):
        # The Google SDK shares an httplib2 transport; it is not thread-safe.
        with self.lock:
            return request.execute()

    @classmethod
    def from_profile(cls, profile):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from google_auth_httplib2 import AuthorizedHttp
        import httplib2
        config = json.loads((profile / "google-calendar-sync.json").read_text())
        credentials = Credentials.from_authorized_user_file(str(profile / "google_token.json"))
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        if not credentials.valid:
            raise ValueError("Google Calendar authentication is unavailable")
        http = AuthorizedHttp(credentials, http=httplib2.Http(timeout=20))
        return cls(config["task_calendar_id"], build("calendar", "v3", http=http, cache_discovery=False))

    def list_events(self, start, end):
        first, last = datetime.fromisoformat(start), datetime.fromisoformat(end)
        if first.tzinfo is None or last.tzinfo is None or first >= last or (last - first).days > 31:
            raise ValueError("calendar window must be timezone-aware and at most 31 days")
        events = []
        token = None
        for _ in range(10):
            result = self._execute(self.service.events().list(calendarId=self.calendar_id, timeMin=start, timeMax=end,
                                                singleEvents=True, orderBy="startTime", maxResults=100,
                                                pageToken=token))
            events.extend(x for x in result.get("items", []) if x.get("status") != "cancelled")
            token = result.get("nextPageToken")
            if not token:
                return events
        raise ValueError("calendar window exceeds 1000 events; use a smaller range")

    def get_event(self, event_id):
        if not isinstance(event_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,1024}", event_id):
            raise ValueError("invalid event ID")
        event = self._execute(self.service.events().get(calendarId=self.calendar_id, eventId=event_id))
        if event.get("status") == "cancelled":
            raise ValueError("event is cancelled")
        return event

    def create_event(self, event_id, title, start, end):
        if not isinstance(event_id, str) or not re.fullmatch(r"[0-9a-v]{5,128}", event_id):
            raise ValueError("invalid stable event ID")
        if not isinstance(title, str) or not title.strip() or len(title) > 300:
            raise ValueError("event title is empty or too long")
        begin, finish = event_interval(start, end)
        fingerprint = hashlib.sha256(json.dumps([title, start, end]).encode()).hexdigest()
        body = {"id": event_id, "summary": title, "start": begin, "end": finish,
                "extendedProperties": {"private": {"catthewTerminal": fingerprint}}}
        try:
            return self._execute(self.service.events().insert(calendarId=self.calendar_id, body=body, sendUpdates="none"))
        except Exception as error:
            if getattr(getattr(error, "resp", None), "status", None) != 409:
                raise
            existing = self._execute(self.service.events().get(calendarId=self.calendar_id, eventId=event_id))
            if existing.get("extendedProperties", {}).get("private", {}).get("catthewTerminal") != fingerprint:
                raise CalendarConflict("event ID belongs to a different operation") from None
            if existing.get("status") == "cancelled":
                raise CalendarConflict("event was cancelled; it will not be recreated") from None
            return existing

    def edit_event(self, event_id, etag, title, start, end):
        """Called only by the private approval surface after single-use consent."""
        if not event_id or not etag or not title or len(title) > 300:
            raise ValueError("event ID, current etag and title are required")
        begin, finish = event_interval(start, end)
        request = self.service.events().patch(calendarId=self.calendar_id, eventId=event_id,
                                             body={"summary": title, "start": begin, "end": finish}, sendUpdates="none")
        request.headers["If-Match"] = _etag(etag)
        return self._execute(request)

    def delete_event(self, event_id, etag):
        """Called only by the private approval surface after single-use consent."""
        if not event_id or not etag:
            raise ValueError("event ID and current etag are required")
        request = self.service.events().delete(calendarId=self.calendar_id, eventId=event_id, sendUpdates="none")
        request.headers["If-Match"] = _etag(etag)
        self._execute(request)
        return {"ok": True, "id": event_id, "deleted": True}
