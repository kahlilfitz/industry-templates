"""Regenerate the Industry Templates mark: four rounded diamonds (toes) above a
rounded chevron pad, laid out on a 1024 grid.

Writes public/paw.svg (the header mark) and public/favicon.svg (a tighter crop so
it still reads at 16px). Run from the repo root:

    python scripts/make-logo.py

The geometry lives in TOES and PAD below as plain vertices plus a corner radius
each; rounded_path() does the arc maths, so the shape can be nudged without
hand-editing SVG path data.
"""
import math, os

R = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public")


def norm(v):
    x, y = v
    m = math.hypot(x, y)
    return (x / m, y / m)


def rounded_path(points, radii):
    """SVG path for a closed polygon with a rounded corner at every vertex.

    `radii` is the arc radius per vertex; the tangent distance along each edge is
    derived from the corner's own angle, and clamped so neighbouring arcs on a
    short edge can never overlap.
    """
    n = len(points)
    segs = []
    tangents = []
    for i in range(n):
        prev, cur, nxt = points[i - 1], points[i], points[(i + 1) % n]
        u = norm((prev[0] - cur[0], prev[1] - cur[1]))
        v = norm((nxt[0] - cur[0], nxt[1] - cur[1]))
        cosang = max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1]))
        half = math.acos(cosang) / 2.0
        d = radii[i] / math.tan(half)
        d = min(d, math.dist(prev, cur) / 2.0, math.dist(cur, nxt) / 2.0)
        r = d * math.tan(half)
        t1 = (cur[0] + u[0] * d, cur[1] + u[1] * d)
        t2 = (cur[0] + v[0] * d, cur[1] + v[1] * d)
        # Sweep direction: cross product of the incoming and outgoing edge
        # directions. Positive turns clockwise in SVG's y-down space.
        a = norm((cur[0] - prev[0], cur[1] - prev[1]))
        b = norm((nxt[0] - cur[0], nxt[1] - cur[1]))
        sweep = 1 if (a[0] * b[1] - a[1] * b[0]) > 0 else 0
        tangents.append((t1, t2, r, sweep))

    f = lambda p: f"{p[0]:.1f} {p[1]:.1f}"
    t1, t2, r, sweep = tangents[0]
    segs.append(f"M{f(t1)}")
    segs.append(f"A{r:.1f} {r:.1f} 0 0 {sweep} {f(t2)}")
    for i in range(1, n):
        t1, t2, r, sweep = tangents[i]
        segs.append(f"L{f(t1)}")
        segs.append(f"A{r:.1f} {r:.1f} 0 0 {sweep} {f(t2)}")
    segs.append("Z")
    return "".join(segs)


def diamond(cx, cy, h, d):
    """A square rotated 45 degrees, with rounded corners — drawn as a path so no
    transform is needed and the gradient stays in user space."""
    pts = [(cx, cy - h), (cx + h, cy), (cx, cy + h), (cx - h, cy)]
    return rounded_path(pts, [d] * 4)


# --- the four toes: centre, half-diagonal, corner radius, gradient id ---------
TOES = [
    # (cx,  cy,   h,   grad, gradient line x1,y1 -> x2,y2, from,      to)
    (211, 476, 114, "t1", (94, 359, 328, 593), "#45cbc0", "#2b9de8"),
    (378, 310, 117, "t2", (261, 193, 495, 427), "#19b9ea", "#2f7bf1"),
    (646, 310, 117, "t3", (529, 427, 763, 193), "#4b7df5", "#8a54f0"),
    (813, 476, 114, "t4", (699, 590, 927, 362), "#7159f2", "#b558e6"),
]

# --- the pad: a chevron, clockwise from the apex -----------------------------
# The apex sits low enough to leave clear air under the two inner toes, and the
# outer edge turns down before it runs into the foot, so the silhouette reads as
# a chevron rather than a rounded triangle.
PAD = [
    ((512, 442), 46),   # apex
    ((786, 700), 56),   # right elbow
    ((786, 776), 62),   # right outer edge, turning down
    ((704, 848), 40),   # right foot, outer
    ((588, 848), 38),   # right foot, inner
    ((512, 742), 38),   # notch
    ((436, 848), 38),   # left foot, inner
    ((320, 848), 40),   # left foot, outer
    ((238, 776), 62),   # left outer edge, turning down
    ((238, 700), 56),   # left elbow
]


def build(view_box):
    defs = []
    shapes = []

    for cx, cy, h, gid, (x1, y1, x2, y2), c0, c1 in TOES:
        defs.append(
            f'    <linearGradient id="{gid}" gradientUnits="userSpaceOnUse" '
            f'x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">\n'
            f'      <stop offset="0" stop-color="{c0}"/>\n'
            f'      <stop offset="1" stop-color="{c1}"/>\n'
            f"    </linearGradient>"
        )
        shapes.append(f'  <path fill="url(#{gid})" d="{diamond(cx, cy, h, 42)}"/>')

    # The pad reads cyan on the left, blue through the apex, purple on the right —
    # the same left-to-right flow the four toes trace.
    defs.append(
        '    <linearGradient id="pad" gradientUnits="userSpaceOnUse" '
        'x1="238" y1="660" x2="786" y2="660">\n'
        '      <stop offset="0" stop-color="#a3e5f2"/>\n'
        '      <stop offset="0.45" stop-color="#3d9df2"/>\n'
        '      <stop offset="1" stop-color="#ab90f7"/>\n'
        "    </linearGradient>"
    )
    pts = [p for p, _ in PAD]
    rads = [r for _, r in PAD]
    shapes.append(f'  <path fill="url(#pad)" d="{rounded_path(pts, rads)}"/>')

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}" '
        'role="img" aria-label="Industry Templates">\n'
        "  <defs>\n" + "\n".join(defs) + "\n  </defs>\n" + "\n".join(shapes) + "\n</svg>\n"
    )


def main():
    # The header mark keeps the artwork's own square framing.
    open(os.path.join(R, "paw.svg"), "w", encoding="utf-8", newline="\n").write(
        build("0 0 1024 1024")
    )
    # The favicon crops in, so the mark still reads at 16px.
    open(os.path.join(R, "favicon.svg"), "w", encoding="utf-8", newline="\n").write(
        build("64 128 896 896")
    )
    for name in ("paw.svg", "favicon.svg"):
        p = os.path.join(R, name)
        print(f"{name:14s} {os.path.getsize(p):5d} bytes")


main()
