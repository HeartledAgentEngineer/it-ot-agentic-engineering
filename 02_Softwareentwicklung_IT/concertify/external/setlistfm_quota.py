"""
external/setlistfm_quota.py
=============================
Daily Request Counter fuer die setlist.fm API.

Hintergrund:
    setlist.fm Free Tier erlaubt 1440 Requests pro Tag (24h, Reset um 00:00 UTC).
    Wenn das ueberschritten wird, gibt es 24h-Sperren (eskaliert von der API).
    Wir wollen das VERMEIDEN, indem wir mitzaehlen und rechtzeitig stoppen.

Engineering-Konzept: "Rate-Limiter Pattern"
    Auch wenn die API selbst rate-limited, sollte unsere Software das mitwissen.
    Sonst geht jeder Request los, kriegt 429, wir verschwenden Zeit + Bandbreite.

Verwendung:
    quota = SetlistFmQuota(Path("setlistfm_quota.json"))
    if quota.can_make_request():
        # API-Call machen
        quota.record_request()
    else:
        # auf morgen warten oder Multi-Source-Fallback
        print(f"Limit erreicht. Reset: {quota.reset_in_seconds()}s")
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


# Setlist.fm Free Tier: 1440 Requests/Tag
# Wir setzen Soft-Limit niedriger um Eskalations-Sperren zu vermeiden.
DAILY_SOFT_LIMIT = 1000  # bei 1000 stoppen — 30% Puffer fuers Web-UI


class SetlistFmQuota:
    """Tracked die taeglichen API-Calls in einer JSON-Datei.

    Format der Datei:
        {
          "date_utc": "2026-05-26",
          "count": 27,
          "last_request_iso": "2026-05-26T14:15:33+00:00"
        }
    """

    def __init__(self, quota_file: Path, soft_limit: int = DAILY_SOFT_LIMIT):
        self._file = quota_file
        self._soft_limit = soft_limit
        self._lock = Lock()

    # ─── Oeffentliche API ───────────────────────────────────────────────────

    def can_make_request(self) -> bool:
        """True wenn das heutige Limit noch nicht erreicht ist."""
        return self.requests_today() < self._soft_limit

    def record_request(self) -> int:
        """Notiert einen API-Call. Returns: aktueller Tageszaehler."""
        with self._lock:
            data = self._load()
            today = self._today_utc()
            if data.get("date_utc") != today:
                # Neuer Tag → reset
                data = {"date_utc": today, "count": 0}
            data["count"] = data.get("count", 0) + 1
            data["last_request_iso"] = datetime.now(timezone.utc).isoformat()
            self._save(data)
            return data["count"]

    def requests_today(self) -> int:
        """Anzahl Requests heute (UTC-Tag)."""
        data = self._load()
        if data.get("date_utc") != self._today_utc():
            return 0
        return data.get("count", 0)

    def remaining_today(self) -> int:
        """Wie viele Requests sind heute noch erlaubt?"""
        return max(0, self._soft_limit - self.requests_today())

    def reset_in_seconds(self) -> int:
        """Sekunden bis 00:00 UTC (Reset-Zeitpunkt)."""
        now = datetime.now(timezone.utc)
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
        # Wir wollen den naechsten Mitternacht-Zeitpunkt:
        from datetime import timedelta
        next_reset = tomorrow + timedelta(days=1)
        return int((next_reset - now).total_seconds())

    def status(self) -> dict:
        """Lesbarer Status fuer Logs / UI."""
        return {
            "date_utc": self._today_utc(),
            "used": self.requests_today(),
            "limit": self._soft_limit,
            "remaining": self.remaining_today(),
            "can_request": self.can_make_request(),
            "reset_in_seconds": self.reset_in_seconds(),
        }

    # ─── Interne Helfer ─────────────────────────────────────────────────────

    def _load(self) -> dict:
        if not self._file.exists():
            return {}
        try:
            return json.loads(self._file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _save(self, data: dict) -> None:
        tmp = self._file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        import os
        os.replace(tmp, self._file)

    @staticmethod
    def _today_utc() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
