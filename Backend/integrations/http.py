import json as jsonlib
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid
from time import monotonic


def _ssl_context() -> ssl.SSLContext:
    """Use certifi CAs when available (fixes macOS Python.org SSL verify failures)."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _encode_multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    """Encode a multipart/form-data body. `files` maps field → (filename, bytes, mime)."""
    boundary = uuid.uuid4().hex
    body = bytearray()
    for name, value in (fields or {}).items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
    for name, (filename, content, mime) in (files or {}).items():
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
            f'filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'
        ).encode()
        body += content
        body += b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return bytes(body), f"multipart/form-data; boundary={boundary}"


class UrllibHttp:
    def __init__(self):
        self._ssl = _ssl_context()

    def json_request(self, method, url, *, headers=None, json=None, files=None, timeout=20):
        started = monotonic()
        payload = None
        req_headers = {"Accept": "application/json", **(headers or {})}
        if files:
            payload, content_type = _encode_multipart({}, files)
            req_headers.setdefault("Content-Type", content_type)
        elif json is not None:
            payload = jsonlib.dumps(json).encode()
            req_headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(url, data=payload, headers=req_headers, method=method)
        try:
            # Audited outbound integration transport; URLs come from trusted client
            # config — scheme restriction belongs in a wrapper, not the transport.
            with urllib.request.urlopen(request, timeout=timeout, context=self._ssl) as response:  # nosec B310
                raw = response.read().decode()
                data = jsonlib.loads(raw) if raw else {}
                self._record(method, url, response.status, started)
                return response.status, data
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode() if exc.fp else ""
            try:
                data = jsonlib.loads(raw) if raw else {}
            except jsonlib.JSONDecodeError:
                data = {"message": raw or str(exc)}
            self._record(method, url, exc.code, started)
            return exc.code, data
        except Exception as exc:
            self._record(method, url, None, started, error=exc)
            raise

    def get_json(self, url, *, headers=None, params=None, timeout=20):
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        return self.json_request("GET", url, headers=headers, timeout=timeout)

    def download(self, url, *, timeout=60) -> bytes:
        """Download binary content (e.g. signed documents) over HTTPS."""
        started = monotonic()
        request = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
        # Signed-document URLs are provider-issued pre-signed HTTPS URLs.
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=self._ssl) as response:  # nosec B310
                payload = response.read()
                self._record("GET", url, response.status, started)
                return payload
        except Exception as exc:
            self._record("GET", url, None, started, error=exc)
            raise

    @staticmethod
    def _record(method, url, status_code, started, *, error=None):
        """Persist metadata only: no query string, headers, request body, or response body."""
        from audit.models import ApiCallLog
        from core.logging import get_log_context

        parsed = urllib.parse.urlsplit(url)
        provider = (parsed.hostname or "unknown")[:100]
        endpoint = f"{parsed.scheme}://{parsed.netloc.split('@')[-1]}{parsed.path}"[:255]
        ApiCallLog.objects.create(
            provider=provider,
            method=str(method).upper()[:10],
            endpoint=endpoint,
            status_code=status_code if isinstance(status_code, int) else None,
            success=bool(status_code is not None and status_code < 400),
            duration_ms=max(0, int((monotonic() - started) * 1000)),
            error_type=type(error).__name__[:80] if error is not None else "",
            request_id=get_log_context().get("request_id", "")[:64],
        )
