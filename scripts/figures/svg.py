"""Tiny SVG drawing helpers so every figure in the book shares one visual language.

Figures are standalone .svg files (they must render on GitHub and in VitePress, in
light and dark mode), so each one carries its own light card background instead of
relying on the page's colors.
"""

from __future__ import annotations

from html import escape

FONT = "-apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', 'Noto Sans CJK SC', 'Noto Sans SC', sans-serif"
MONO = "'JetBrains Mono', Menlo, Consolas, 'Noto Sans Mono CJK SC', monospace"

INK = "#1f2937"
MUTED = "#6b7280"
FAINT = "#9ca3af"
CARD = "#ffffff"
CARD_STROKE = "#e5e7eb"

# tone -> (fill, stroke, text)
TONES = {
    "neutral": ("#f8fafc", "#94a3b8", INK),
    "accent": ("#eff6ff", "#2563eb", "#1e3a8a"),
    "ok": ("#f0fdf4", "#16a34a", "#14532d"),
    "warn": ("#fffbeb", "#d97706", "#78350f"),
    "bad": ("#fef2f2", "#dc2626", "#7f1d1d"),
    "purple": ("#f5f3ff", "#7c3aed", "#4c1d95"),
    "teal": ("#f0fdfa", "#0d9488", "#134e4a"),
    "muted": ("#f9fafb", "#d1d5db", FAINT),
    "dark": ("#1f2937", "#1f2937", "#ffffff"),
}
LINE = {
    "neutral": "#64748b",
    "accent": "#2563eb",
    "ok": "#16a34a",
    "warn": "#d97706",
    "bad": "#dc2626",
    "purple": "#7c3aed",
    "teal": "#0d9488",
    "muted": "#cbd5e1",
}


def text_width(s: str, size: float) -> float:
    w = 0.0
    for ch in s:
        w += size if ord(ch) > 0x2E80 else size * 0.58
    return w


class Fig:
    def __init__(self, w: int, h: int, label: str) -> None:
        self.w, self.h, self.label = w, h, label
        self.parts: list[str] = []
        self.warnings: list[str] = []

    # ------------------------------------------------------------ primitives
    def text(self, x, y, s, size=12, anchor="middle", color=INK, weight=None, mono=False, italic=False):
        attrs = f'x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{color}"'
        if weight:
            attrs += f' font-weight="{weight}"'
        if mono:
            attrs += f' font-family="{MONO}"'
        if italic:
            attrs += ' font-style="italic"'
        self.parts.append(f"<text {attrs}>{escape(s)}</text>")

    def lines(self, x, y, rows, size=12, gap=None, **kw):
        gap = gap or size * 1.35
        for i, r in enumerate(rows):
            self.text(x, y + i * gap, r, size=size, **kw)

    def rect(self, x, y, w, h, fill="none", stroke=INK, rx=8, dashed=False, sw=1.5):
        d = ' stroke-dasharray="5 4"' if dashed else ""
        self.parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>'
        )

    def box(self, x, y, w, h, label, sub=None, tone="neutral", rx=8, dashed=False, size=13, mono=False, bold=True):
        fill, stroke, color = TONES[tone]
        self.rect(x, y, w, h, fill=fill, stroke=stroke, rx=rx, dashed=dashed)
        rows = label.split("\n")
        sub_rows = sub.split("\n") if sub else []
        total = len(rows) * size * 1.3 + len(sub_rows) * (size - 2) * 1.3
        cy = y + h / 2 - total / 2 + size * 0.95
        for r in rows:
            if text_width(r, size) > w - 8:
                self.warnings.append(f"overflow: {r!r} in box w={w}")
            self.text(x + w / 2, cy, r, size=size, color=color, weight="600" if bold else None, mono=mono)
            cy += size * 1.3
        for r in sub_rows:
            if text_width(r, size - 2) > w - 8:
                self.warnings.append(f"overflow: {r!r} in box w={w}")
            self.text(x + w / 2, cy, r, size=size - 2, color=MUTED if tone != "dark" else "#d1d5db", mono=mono)
            cy += (size - 2) * 1.3
        return (x, y, w, h)

    def group(self, x, y, w, h, title, tone="neutral", dashed=True):
        stroke = LINE.get(tone, "#94a3b8")
        self.rect(x, y, w, h, fill="none", stroke=stroke, rx=12, dashed=dashed, sw=1.2)
        self.text(x + 12, y + 18, title, size=12, anchor="start", color=stroke, weight="600")

    def arrow(self, pts, label=None, tone="neutral", dashed=False, both=False, label_at=0.5, label_dx=0, label_dy=-6,
              size=11, sw=1.6, label_anchor="middle"):
        color = LINE[tone]
        d = " ".join(("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        start = f' marker-start="url(#a-{tone}-s)"' if both else ""
        self.parts.append(
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{dash} marker-end="url(#a-{tone})"{start}/>'
        )
        if label:
            # place label at fraction of total path length
            segs = list(zip(pts, pts[1:]))
            lens = [((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 for (x1, y1), (x2, y2) in segs]
            target = sum(lens) * label_at
            acc = 0
            for ((x1, y1), (x2, y2)), L in zip(segs, lens):
                if acc + L >= target:
                    t = (target - acc) / (L or 1)
                    lx, ly = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
                    break
                acc += L
            # background pill for readability
            tw = text_width(label, size) + 8
            bx = lx + label_dx - (tw / 2 if label_anchor == "middle" else 0)
            self.parts.append(
                f'<rect x="{bx:.1f}" y="{ly + label_dy - size + 1:.1f}" width="{tw:.1f}" height="{size + 4}" rx="3" fill="{CARD}" opacity="0.92"/>'
            )
            self.text(bx + tw / 2, ly + label_dy + 1.5, label, size=size, color=color if tone != "muted" else MUTED)

    def line(self, x1, y1, x2, y2, color=CARD_STROKE, sw=1, dashed=False):
        dash = ' stroke-dasharray="4 4"' if dashed else ""
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}"{dash}/>')

    def circle(self, cx, cy, r, tone="neutral", label=None, size=11):
        fill, stroke, color = TONES[tone]
        self.parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        if label:
            self.text(cx, cy + size * 0.35, label, size=size, color=color, weight="600")

    def raw(self, s: str):
        self.parts.append(s)

    def title(self, s, sub=None):
        self.text(24, 34, s, size=15, anchor="start", weight="700")
        if sub:
            self.text(24, 54, sub, size=12, anchor="start", color=MUTED)

    # ------------------------------------------------------------ output
    def svg(self) -> str:
        markers = []
        for tone, color in LINE.items():
            markers.append(
                f'<marker id="a-{tone}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                f'<path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
                f'<marker id="a-{tone}-s" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                f'<path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
            )
        body = "\n".join(self.parts)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
            f'role="img" aria-label="{escape(self.label)}" font-family="{FONT}">\n'
            f"<title>{escape(self.label)}</title>\n<defs>{''.join(markers)}</defs>\n"
            f'<rect x="0.5" y="0.5" width="{self.w - 1}" height="{self.h - 1}" rx="14" fill="{CARD}" stroke="{CARD_STROKE}"/>\n'
            f"{body}\n</svg>\n"
        )
