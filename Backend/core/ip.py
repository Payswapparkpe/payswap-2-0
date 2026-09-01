import ipaddress

from django.conf import settings


def parse_ip_networks(raw_values) -> tuple[ipaddress._BaseNetwork, ...]:
    networks = []
    for value in raw_values or []:
        item = (value or "").strip()
        if not item:
            continue
        if "/" not in item:
            item = f"{item}/32" if ":" not in item else f"{item}/128"
        networks.append(ipaddress.ip_network(item, strict=False))
    return tuple(networks)


def client_ip(request) -> str:
    if getattr(settings, "ADMIN_TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


def ip_is_allowed(ip_value: str, networks) -> bool:
    if not ip_value:
        return False
    try:
        address = ipaddress.ip_address(ip_value)
    except ValueError:
        return False
    if address.version == 6 and address.ipv4_mapped:
        address = address.ipv4_mapped
    return any(address in network for network in networks)
