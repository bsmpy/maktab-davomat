"""Hikvision ISAPI client (tested against DS-K1T341CMF).

Everything the platform needs from an access terminal:

* ``device_info``   – reachability + firmware, used by the "Tekshirish" button
* ``search_events`` – pull access records (``AcsEvent``), paged
* ``upsert_person`` – create/update the person record an event references
* ``upload_face``   – enrol a face picture into the device's FD library
* ``delete_person`` – remove a person and their face
* ``sync_time``     – align the device clock with Asia/Tashkent

ISAPI speaks HTTP digest auth and answers JSON when ``?format=json`` is passed.
Devices are on the LAN, so timeouts are short and every call is wrapped: a
turnstile being unplugged must never surface as a 500 in the cabinet.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10.0
#: The device caps a single AcsEvent search at 30 records.
EVENT_PAGE_SIZE = 30
#: Guard against a misconfigured device paging forever.
MAX_EVENT_PAGES = 200


class HikvisionError(Exception):
    """Any failure talking to a device, normalised to a readable message.

    The device explains itself in the response body (``employeeNoAlreadyExist``,
    ``methodNotAllowed``, …). That explanation is carried here rather than
    thrown away, because "HTTP 400" on its own is undiagnosable.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        unauthorized: bool = False,
        sub_status: str = "",
        payload: dict | None = None,
    ):
        self.status = status
        self.unauthorized = unauthorized
        self.sub_status = sub_status
        self.payload = payload or {}
        super().__init__(message)

    @property
    def is_duplicate(self) -> bool:
        """The record already exists — an update, not a failure."""
        return _is_duplicate(self.payload)


@dataclass(frozen=True)
class DeviceInfo:
    name: str
    model: str
    serial_number: str
    firmware: str
    mac: str

    @classmethod
    def from_payload(cls, payload: dict) -> DeviceInfo:
        info = payload.get("DeviceInfo", payload)
        return cls(
            name=str(info.get("deviceName", "")),
            model=str(info.get("model", "")),
            serial_number=str(info.get("serialNumber", "")),
            firmware=str(info.get("firmwareVersion", "")),
            mac=str(info.get("macAddress", "")),
        )


@dataclass(frozen=True)
class AccessEvent:
    """One normalised access record."""

    external_id: str
    occurred_at: datetime
    person_code: str
    person_name: str
    minor: int
    attendance_status: str
    verify_mode: str
    picture_url: str
    raw: dict


def _parse_device_time(value: str) -> datetime | None:
    """ISAPI emits ``2026-09-08T08:31:02+05:00`` (sometimes without the offset)."""
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(text[:19], fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if timezone.is_naive(parsed):
        # A device without an offset is configured in local school time.
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


class HikvisionClient:
    """Thin ISAPI wrapper. Construct from a ``Terminal`` with ``for_terminal``."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        verify_tls: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            auth=httpx.DigestAuth(username, password),
            timeout=timeout,
            # LAN devices ship self-signed certificates; the channel is a
            # private network segment, not the public internet.
            verify=verify_tls,
            follow_redirects=False,
        )

    @classmethod
    def for_terminal(cls, terminal, **kwargs) -> HikvisionClient:
        return cls(
            terminal.base_url,
            terminal.username,
            terminal.password,
            verify_tls=bool(terminal.use_https and kwargs.pop("verify_tls", False)),
            **kwargs,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HikvisionClient:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # --- transport ------------------------------------------------------ #
    def _request(self, method: str, path: str, **kwargs) -> Any:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise HikvisionError(
                f"Qurilmaga ulanib bo'lmadi: {exc.__class__.__name__}"
            ) from exc

        if response.status_code in (401, 403):
            raise HikvisionError(
                "Login yoki parol noto'g'ri.", status=response.status_code, unauthorized=True
            )
        if response.status_code >= 400:
            sub_status, payload = _error_detail(response)
            raise HikvisionError(
                f"Qurilma xatolik qaytardi (HTTP {response.status_code})"
                + (f": {sub_status}" if sub_status else "")
                + ".",
                status=response.status_code,
                sub_status=sub_status,
                payload=payload,
            )

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            # Some endpoints answer XML even when JSON was requested.
            return {"raw": response.text}

    def _get(self, path: str, **kwargs) -> Any:
        return self._request("GET", path, **kwargs)

    def _post(self, path: str, **kwargs) -> Any:
        return self._request("POST", path, **kwargs)

    def _put(self, path: str, **kwargs) -> Any:
        return self._request("PUT", path, **kwargs)

    # --- device --------------------------------------------------------- #
    def device_info(self) -> DeviceInfo:
        return DeviceInfo.from_payload(self._get("/ISAPI/System/deviceInfo?format=json"))

    def sync_time(self, moment: datetime | None = None) -> None:
        """Push local time to the device — clock drift corrupts attendance."""
        moment = timezone.localtime(moment or timezone.now())
        self._put(
            "/ISAPI/System/time?format=json",
            json={
                "Time": {
                    "timeMode": "manual",
                    "localTime": moment.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": _posix_timezone(moment),
                }
            },
        )

    # --- events --------------------------------------------------------- #
    def search_events(
        self,
        start: datetime,
        end: datetime,
        *,
        page_size: int = EVENT_PAGE_SIZE,
        search_id: str = "attendance-sync",
    ) -> Iterator[AccessEvent]:
        """Yield every access record in ``[start, end]``, paging as needed."""
        position = 0
        for _page in range(MAX_EVENT_PAGES):
            payload = {
                "AcsEventCond": {
                    "searchID": search_id,
                    "searchResultPosition": position,
                    "maxResults": page_size,
                    "major": 5,  # event category: access control
                    "minor": 0,  # 0 = every minor type
                    "startTime": _isapi_time(start),
                    "endTime": _isapi_time(end),
                }
            }
            result = self._post("/ISAPI/AccessControl/AcsEvent?format=json", json=payload)
            block = result.get("AcsEvent", {}) if isinstance(result, dict) else {}
            records = block.get("InfoList") or []

            for record in records:
                event = self._normalise_event(record)
                if event is not None:
                    yield event

            num_matches = int(block.get("numOfMatches") or len(records))
            total = int(block.get("totalMatches") or 0)
            position += num_matches or len(records)

            status = str(block.get("responseStatusStrg", "")).upper()
            if not records or status == "OK" or (total and position >= total):
                return
        logger.warning("AcsEvent paging hit the page cap for %s", self.base_url)

    def _normalise_event(self, record: dict) -> AccessEvent | None:
        occurred_at = _parse_device_time(str(record.get("time", "")))
        if occurred_at is None:
            return None

        person_code = str(record.get("employeeNoString") or record.get("employeeNo") or "").strip()
        serial = record.get("serialNo")
        # A device-side serial is the best idempotency key; when it is missing
        # (older firmware) fall back to person + timestamp, which is unique in
        # practice because the turnstile debounces repeat reads.
        external_id = (
            f"sn:{serial}" if serial not in (None, "", 0) else f"tm:{person_code}:{occurred_at.isoformat()}"
        )

        picture = str(record.get("pictureURL") or "")
        return AccessEvent(
            external_id=external_id[:128],
            occurred_at=occurred_at,
            person_code=person_code[:64],
            person_name=str(record.get("name") or "")[:150],
            minor=int(record.get("minor") or 0),
            attendance_status=str(record.get("attendanceStatus") or ""),
            verify_mode=str(record.get("currentVerifyMode") or record.get("verifyMode") or ""),
            picture_url=picture if picture.startswith("http") else "",
            raw=record,
        )

    # --- people --------------------------------------------------------- #
    def upsert_person(
        self,
        person_code: str,
        name: str,
        *,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        user_type: str = "normal",
    ) -> None:
        """Create the person, or update them if the device already has the code."""
        begin = valid_from or timezone.localtime()
        end = valid_to or (begin + timedelta(days=365 * 5))
        payload = {
            "UserInfo": {
                "employeeNo": str(person_code),
                "name": name[:32],
                "userType": user_type,
                "Valid": {
                    "enable": True,
                    "beginTime": begin.strftime("%Y-%m-%dT%H:%M:%S"),
                    "endTime": end.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeType": "local",
                },
                "doorRight": "1",
                "RightPlan": [{"doorNo": 1, "planTemplateNo": "1"}],
            }
        }
        # The device reports a duplicate as HTTP 400 with
        # ``employeeNoAlreadyExist``, so the answer has to be read off the
        # exception as well as off a 200 body.
        try:
            result = self._post("/ISAPI/AccessControl/UserInfo/Record?format=json", json=payload)
        except HikvisionError as error:
            if not error.is_duplicate:
                raise
            result = error.payload

        if _is_duplicate(result):
            self._put("/ISAPI/AccessControl/UserInfo/Modify?format=json", json=payload)

    def delete_person(self, person_code: str) -> None:
        self._put(
            "/ISAPI/AccessControl/UserInfo/Delete?format=json",
            json={"UserInfoDelCond": {"EmployeeNoList": [{"employeeNo": str(person_code)}]}},
        )

    def upload_face(self, person_code: str, image: bytes, *, fdid: str = "1") -> None:
        """Enrol a face picture. The person record must already exist.

        Access terminals expose the face library as ``FaceDataRecord``;
        ``FDSetUp`` is the camera/NVR spelling and answers ``methodNotAllowed``
        on a DS-K1T341CMF. Both are tried so either family works.
        """

        def _body() -> dict:
            # Rebuilt per attempt: httpx consumes the parts as it sends them.
            return {
                "FaceDataRecord": (
                    None,
                    _json_dumps(
                        {"faceLibType": "blackFD", "FDID": fdid, "FPID": str(person_code)}
                    ),
                    "application/json",
                ),
                "img": ("face.jpg", image, "image/jpeg"),
            }

        try:
            self._post("/ISAPI/Intelligent/FDLib/FaceDataRecord?format=json", files=_body())
            return
        except HikvisionError as error:
            if error.sub_status == "methodNotAllowed":
                # Camera/NVR firmware spells the same library differently.
                self._post("/ISAPI/Intelligent/FDLib/FDSetUp?format=json", files=_body())
                return
            if error.sub_status != "deviceUserAlreadyExistFace":
                raise

        # The pupil already has a face on this device. Re-enrolling means the
        # photo changed, so replace it rather than reporting a failure.
        self.delete_face(str(person_code), fdid=fdid)
        self._post("/ISAPI/Intelligent/FDLib/FaceDataRecord?format=json", files=_body())

    def delete_face(self, person_code: str, *, fdid: str = "1") -> None:
        self._put(
            "/ISAPI/Intelligent/FDLib/FDSearch/Delete?format=json&FDID="
            f"{fdid}&faceLibType=blackFD",
            json={"FPID": [{"value": str(person_code)}]},
        )

    def person_count(self) -> int:
        result = self._get("/ISAPI/AccessControl/UserInfo/Count?format=json")
        return int((result.get("UserInfoCount") or {}).get("userNumber") or 0)


def _json_dumps(value: dict) -> str:
    import json

    return json.dumps(value)


def _error_detail(response) -> tuple[str, dict]:
    """Pull the device's own reason out of an error response."""
    try:
        payload = response.json()
    except ValueError:
        return "", {}
    if not isinstance(payload, dict):
        return "", {}
    reason = str(payload.get("subStatusCode") or payload.get("statusString") or "")
    return reason, payload


def _is_duplicate(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    status = result.get("statusCode")
    message = str(result.get("subStatusCode") or result.get("statusString") or "").lower()
    return status == 6 or "exist" in message or "duplicate" in message


def _isapi_time(moment: datetime) -> str:
    local = timezone.localtime(moment)
    return local.strftime("%Y-%m-%dT%H:%M:%S") + _offset_suffix(local)


def _offset_suffix(moment: datetime) -> str:
    offset = moment.utcoffset() or timedelta(0)
    total = int(offset.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"


def _posix_timezone(moment: datetime) -> str:
    """Hikvision expects POSIX-style ``CST-5:00:00`` (sign inverted)."""
    offset = moment.utcoffset() or timedelta(0)
    total = int(offset.total_seconds())
    sign = "-" if total >= 0 else "+"
    total = abs(total)
    return f"CST{sign}{total // 3600}:{(total % 3600) // 60:02d}:00"
