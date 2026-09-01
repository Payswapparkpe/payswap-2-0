def attach_pct(rows, key="total"):
    items = list(rows)
    peak = max((int(item.get(key) or 0) for item in items), default=0) or 1
    for item in items:
        item["pct"] = int(round(100 * int(item.get(key) or 0) / peak))
    return items
