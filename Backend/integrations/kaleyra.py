from .http import UrllibHttp


class KaleyraError(Exception):
    pass


class KaleyraClient:
    def __init__(self, *, sid, api_key, sender, base_url="https://api.in.kaleyra.io", http=None):
        self.sid = sid
        self.api_key = api_key
        self.sender = sender
        self.base_url = base_url.rstrip("/")
        self.http = http or UrllibHttp()

    @property
    def configured(self) -> bool:
        return bool(self.sid and self.api_key and self.sender)

    def send_sms(
        self,
        *,
        to: str,
        body: str,
        sms_type: str = "OTP",
        template_id: str = "",
        entity_id: str = "",
    ):
        if not self.configured:
            raise KaleyraError("Kaleyra SMS is not configured.")
        digits = "".join(ch for ch in to if ch.isdigit())
        if len(digits) == 10:
            digits = f"91{digits}"
        to_number = digits if digits.startswith("+") else f"+{digits}"
        # Payload matches Kaleyra's JSON/XML SMS API, not /messages (form) or /messages/json.
        url = f"{self.base_url}/v1/{self.sid}/sms/json"
        sms_node = {"to": to_number, "from": self.sender, "body": body}
        payload = {
            "channel": "SMS",
            "type": sms_type,
            "source": "API",
            "from": self.sender,
            "body": body,
            "sms": [sms_node],
        }
        if template_id:
            payload["template_id"] = template_id
            sms_node["template_id"] = template_id
        if entity_id:
            payload["entity_id"] = entity_id
            sms_node["entity_id"] = entity_id
        status, data = self.http.json_request(
            "POST",
            url,
            headers={"api-key": self.api_key},
            json=payload,
        )
        if status >= 400:
            err = data.get("message")
            if not err and isinstance(data.get("error"), dict):
                err = data["error"].get("message")
            raise KaleyraError(err or f"Kaleyra rejected the SMS ({status}).")
        return data
