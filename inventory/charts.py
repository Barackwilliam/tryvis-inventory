"""
Charts, drawn as inline SVG on the server.

No chart library, no extra request, nothing to load before the page is
readable. Every function returns plain data the template prints, and returns
None when there is not enough to draw — so the template shows an empty state
instead of an empty box.
"""
from decimal import Decimal

BLUE = "#2563EB"
SKY = "#38BDF8"
GREEN = "#16A34A"
AMBER = "#F59E0B"
RED = "#DC2626"
SLATE = "#94A3B8"

PALETTE = [BLUE, SKY, GREEN, AMBER, "#8B5CF6", "#EC4899", "#14B8A6", SLATE]


def _floats(values):
    return [float(v or 0) for v in values]


def line_chart(points, width=640, height=180, tone=BLUE, fill_id="fill"):
    """points: [{"label": str, "value": number}] — oldest first."""
    if len(points) < 2:
        return None

    values = _floats(p["value"] for p in points)
    low, high = min(values), max(values)
    if high == low:
        high = low + 1
    pad_x, pad_y = 8, 14
    span_x, span_y = width - pad_x * 2, height - pad_y * 2

    coords = [
        (
            round(pad_x + span_x * i / (len(values) - 1), 1),
            round(pad_y + span_y * (1 - (v - low) / (high - low)), 1),
        )
        for i, v in enumerate(values)
    ]
    line = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(coords))

    return {
        "width": width,
        "height": height,
        "line": line,
        "area": line + f" L{coords[-1][0]},{height} L{coords[0][0]},{height} Z",
        "dots": "".join(f'<circle cx="{x}" cy="{y}" r="3" fill="{tone}" />' for x, y in coords[-1:]),
        "tone": tone,
        "fill_id": fill_id,
        "labels": [{"x": coords[i][0], "text": p["label"]} for i, p in enumerate(points)],
    }


def grouped_bars(rows, series, width=640, height=190):
    """
    rows:   [{"label": str, <key>: number, ...}]
    series: [(key, colour, human name)]
    """
    if not rows:
        return None

    peak = max(_floats(r[key] for r in rows for key, _, _ in series) + [1])
    pad_y = 18
    span_y = height - pad_y - 22
    group_w = width / len(rows)
    bar_w = min(20, group_w / (len(series) + 1.6))
    gap = 4
    block = len(series) * bar_w + (len(series) - 1) * gap

    bars = []
    for index, row in enumerate(rows):
        left = group_w * (index + 0.5) - block / 2
        for position, (key, colour, name) in enumerate(series):
            value = float(row.get(key) or 0)
            bar_h = max(2, span_y * value / peak) if value else 2
            bars.append({
                "x": round(left + position * (bar_w + gap), 1),
                "y": round(pad_y + span_y - bar_h, 1),
                "w": round(bar_w, 1),
                "h": round(bar_h, 1),
                "tone": colour,
                "faint": value == 0,
                "title": f"{row['label']} · {name}: {value:,.0f}",
            })

    return {
        "width": width,
        "height": height,
        "bars": bars,
        "baseline": round(pad_y + span_y, 1),
        "labels": [{"x": round(group_w * (i + .5), 1), "text": r["label"]} for i, r in enumerate(rows)],
        "legend": [{"name": name, "tone": colour} for _, colour, name in series],
    }


def signed_bars(rows, width=640, height=190, up=GREEN, down=RED):
    """Bars that can go below the line — profit, gains and losses."""
    if not rows:
        return None

    values = _floats(r["value"] for r in rows)
    peak = max([abs(v) for v in values] + [1])
    pad_y = 16
    span = (height - pad_y - 22) / 2
    zero = pad_y + span
    group_w = width / len(rows)
    bar_w = min(28, group_w * 0.46)

    bars = []
    for index, row in enumerate(rows):
        value = float(row["value"] or 0)
        bar_h = max(2, span * abs(value) / peak)
        bars.append({
            "x": round(group_w * (index + .5) - bar_w / 2, 1),
            "y": round(zero - bar_h if value >= 0 else zero, 1),
            "w": round(bar_w, 1),
            "h": round(bar_h, 1),
            "tone": up if value >= 0 else down,
            "title": f"{row['label']}: {value:,.0f}",
        })

    return {
        "width": width, "height": height, "bars": bars, "baseline": round(zero, 1),
        "labels": [{"x": round(group_w * (i + .5), 1), "text": r["label"]} for i, r in enumerate(rows)],
    }


def donut(slices, size=132, thickness=13):
    """slices: [{"label": str, "value": number, "colour": str}] — largest first."""
    slices = [s for s in slices if float(s["value"] or 0) > 0]
    if not slices:
        return None

    total = sum(float(s["value"]) for s in slices)
    radius = (size - thickness) / 2
    circumference = 2 * 3.14159265 * radius

    arcs, offset = [], 0.0
    for piece in slices:
        share = float(piece["value"]) / total
        length = circumference * share
        arcs.append({
            "colour": piece["colour"],
            "dash": f"{length:.2f} {circumference - length:.2f}",
            "offset": f"{-offset:.2f}",
            "label": piece["label"],
            "percent": round(share * 100, 1),
            "value": piece["value"],
        })
        offset += length

    return {
        "size": size,
        "centre": size / 2,
        "radius": round(radius, 1),
        "thickness": thickness,
        "arcs": arcs,
        "total": total,
    }


def horizontal_bars(rows, limit=8, tone=None):
    """rows: [{"label": str, "value": number}] — drawn as CSS bars, not SVG."""
    rows = [r for r in rows if float(r["value"] or 0) > 0]
    if not rows:
        return []
    rows = sorted(rows, key=lambda r: float(r["value"]), reverse=True)[:limit]
    peak = float(rows[0]["value"])
    return [
        {
            "label": r["label"],
            "value": r["value"],
            "percent": round(float(r["value"]) / peak * 100, 1),
            "tone": tone or PALETTE[i % len(PALETTE)],
        }
        for i, r in enumerate(rows)
    ]


def sparkline(values, width=120, height=32, tone=BLUE):
    """A tiny line for inside a card. Values oldest first."""
    values = _floats(values)
    if len(values) < 2:
        return None
    low, high = min(values), max(values)
    if high == low:
        high = low + 1
    points = " ".join(
        f"{'M' if i == 0 else 'L'}{round(width * i / (len(values) - 1), 1)},"
        f"{round(height - 3 - (height - 6) * (v - low) / (high - low), 1)}"
        for i, v in enumerate(values)
    )
    return {"width": width, "height": height, "line": points, "tone": tone}
