"""India Post PIN-code lookup backed by the public postalpincode.in API.

Results are cached for 30 days (PIN geographies change rarely) so onboarding
forms stay fast and the upstream service is not hammered per keystroke.
"""

from django.core.cache import cache
from django.core.exceptions import ValidationError

from .http import UrllibHttp

CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
API_URL = "https://api.postalpincode.in/pincode/{pin}"


class PostalService:
    @staticmethod
    def lookup(pincode: str, *, client=None) -> dict:
        pin = "".join(ch for ch in (pincode or "") if ch.isdigit())
        if len(pin) != 6:
            raise ValidationError("Enter a valid PIN code.")
        cache_key = f"pincode:{pin}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        client = client or UrllibHttp()
        try:
            status, data = client.json_request("GET", API_URL.format(pin=pin), timeout=10)
        except Exception as exc:
            raise ValidationError("Could not validate the PIN code right now. Try again.") from exc
        if status != 200 or not isinstance(data, list) or not data:
            raise ValidationError("Could not validate the PIN code right now. Try again.")
        entry = data[0]
        if entry.get("Status") != "Success" or not entry.get("PostOffice"):
            raise ValidationError("This PIN code was not found. Check and try again.")
        office = entry["PostOffice"][0]
        result = {
            "pincode": pin,
            "district": office.get("District") or "",
            "state": office.get("State") or "",
            "area": office.get("Name") or "",
        }
        cache.set(cache_key, result, timeout=CACHE_TTL_SECONDS)
        return result
