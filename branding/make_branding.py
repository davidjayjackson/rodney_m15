"""Generate the project logo and banner as SVG.

Star brightnesses come from the real per-star mean magnitudes in the database.
Positions are synthetic - the AAVSO reports carry no coordinates - and follow a
centrally concentrated profile in keeping with M15, a core-collapsed cluster.

    python branding/make_branding.py

Writes branding/logo.svg and branding/banner.svg.  Deterministic: the same
database produces the same image every run.
"""

import math
import random
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_HOME = HERE.parent
DATABASE = PROJECT_HOME / 'NGC7078.sqlite'

# Deep space, kept dark so the image reads the same on light and dark pages.
INK_OUTER = '#05070f'
INK_INNER = '#101c33'
ACCENT = '#7fb2ff'   # blue-white main sequence
WARM = '#ffd9ab'     # red giant branch
TEXT = '#e8eeff'
MUTED = '#8fa3c8'


def star_magnitudes():
    """Mean magnitude per star, brightest first.  Falls back if no database."""
    if not DATABASE.exists():
        print('No database at %s - using a synthetic magnitude spread.' % DATABASE)
        return [-4.0 + 0.03 * i for i in range(241)]
    connection = sqlite3.connect(DATABASE)
    rows = connection.execute(
        'select avg(MAG) from Sloan_SG where MAG is not null'
        ' group by STARNAME order by avg(MAG)'
    ).fetchall()
    connection.close()
    return [r[0] for r in rows]


def cluster_points(count, rng, concentration=2.4):
    """Radial positions in [0, 1], bunched towards the centre."""
    points = []
    for _ in range(count):
        # u**concentration pushes most stars inwards; the tail gives a halo.
        radius = rng.random() ** concentration
        angle = rng.uniform(0, 2 * math.pi)
        points.append((radius * math.cos(angle), radius * math.sin(angle), radius))
    return points


def star_svg(cx, cy, size, colour, opacity):
    """A star as a soft dot; the brightest get a cross-hair diffraction spike."""
    parts = ['<circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s" opacity="%.2f"/>'
             % (cx, cy, size, colour, opacity)]
    if size > 2.6:
        arm = size * 4.5
        parts.append(
            '<path d="M%.2f %.2f h%.2f M%.2f %.2f v%.2f" stroke="%s"'
            ' stroke-width="%.2f" opacity="%.2f" stroke-linecap="round"/>'
            % (cx - arm / 2, cy, arm, cx, cy - arm / 2, arm,
               colour, size * 0.22, opacity * 0.5)
        )
    return ''.join(parts)


def render_cluster(mags, cx, cy, scale, rng, size_boost=1.0, concentration=1.5):
    """Draw one star per magnitude, sized by brightness."""
    brightest, faintest = min(mags), max(mags)
    span = faintest - brightest or 1.0
    points = cluster_points(len(mags), rng, concentration)

    # Brightest stars sit nearer the centre, as in a relaxed cluster, but the
    # jitter keeps it from looking like a mechanically sorted gradient.
    order = sorted(range(len(mags)), key=lambda i: mags[i])
    points.sort(key=lambda p: p[2] + rng.gauss(0, 0.22))

    out = []
    for rank, index in enumerate(order):
        x, y, _radius = points[rank]
        weight = 1.0 - (mags[index] - brightest) / span     # 1 = brightest
        size = (1.0 + 3.6 * weight ** 1.7) * size_boost
        opacity = 0.5 + 0.5 * weight ** 0.7
        # A minority of giants, as in a real cluster - enough to warm the core
        # without turning it orange.
        colour = WARM if rng.random() < 0.08 + 0.14 * weight else ACCENT
        out.append(star_svg(cx + x * scale, cy + y * scale, size, colour, opacity))
    return '\n'.join(out)


def defs(prefix, glow_r=0.5):
    """Gradients, namespaced so logo and banner can coexist in one page."""
    return '''<defs>
<radialGradient id="%(p)ssky" cx="50%%" cy="50%%" r="75%%">
  <stop offset="0%%" stop-color="%(inner)s"/>
  <stop offset="100%%" stop-color="%(outer)s"/>
</radialGradient>
<radialGradient id="%(p)sglow" cx="50%%" cy="50%%" r="%(gr)s%%">
  <stop offset="0%%" stop-color="%(accent)s" stop-opacity="0.55"/>
  <stop offset="45%%" stop-color="%(accent)s" stop-opacity="0.13"/>
  <stop offset="100%%" stop-color="%(accent)s" stop-opacity="0"/>
</radialGradient>
</defs>''' % {'p': prefix, 'inner': INK_INNER, 'outer': INK_OUTER,
              'accent': ACCENT, 'gr': int(glow_r * 100)}


def make_logo(mags, path):
    size = 512
    c = size / 2
    rng = random.Random(7)
    body = render_cluster(mags, c, c, scale=205, rng=rng, size_boost=1.6,
                          concentration=1.25)

    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" \
width="512" height="512" role="img" aria-label="NGC 7078 star cluster logo">
%(defs)s
<circle cx="256" cy="256" r="248" fill="url(#lgsky)"/>
<circle cx="256" cy="256" r="248" fill="url(#lgglow)"/>
%(stars)s
<circle cx="256" cy="256" r="248" fill="none" stroke="%(accent)s" \
stroke-opacity="0.35" stroke-width="3"/>
<circle cx="256" cy="256" r="236" fill="none" stroke="%(accent)s" \
stroke-opacity="0.13" stroke-width="1.5"/>
</svg>
''' % {'defs': defs('lg', 0.42), 'stars': body, 'accent': ACCENT}
    path.write_text(svg, encoding='utf-8')


def make_banner(mags, path):
    width, height = 1200, 320
    rng = random.Random(11)
    cluster = render_cluster(mags, 196, height / 2, scale=136, rng=rng,
                             size_boost=1.25, concentration=1.3)

    # A sparse field of foreground stars across the rest of the banner.
    field = []
    for _ in range(90):
        x = rng.uniform(380, width - 20)
        y = rng.uniform(12, height - 12)
        s = rng.choice([0.5, 0.6, 0.8, 1.0, 1.3])
        field.append(star_svg(x, y, s, ACCENT, rng.uniform(0.12, 0.5)))

    font = 'font-family="Segoe UI,Helvetica Neue,Arial,sans-serif"'
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 320" \
width="1200" height="320" role="img" \
aria-label="NGC 7078 - M15 Sloan g photometry importer">
%(defs)s
<rect width="1200" height="320" fill="url(#bnsky)"/>
<ellipse cx="196" cy="160" rx="300" ry="220" fill="url(#bnglow)"/>
%(field)s
%(cluster)s
<text x="404" y="132" %(font)s font-size="62" font-weight="600" \
fill="%(text)s" letter-spacing="1.5">NGC 7078</text>
<text x="404" y="176" %(font)s font-size="25" fill="%(accent)s" \
letter-spacing="0.6">M15 &#183; Sloan g photometry importer</text>
<line x1="405" y1="206" x2="700" y2="206" stroke="%(accent)s" stroke-opacity="0.3"/>
<text x="404" y="240" %(font)s font-size="19" fill="%(muted)s" \
letter-spacing="0.4">241 stars &#183; 16,388 measurements &#183; 5 nights \
&#183; SQLite</text>
</svg>
''' % {'defs': defs('bn', 0.5), 'field': '\n'.join(field), 'cluster': cluster,
       'font': font, 'text': TEXT, 'accent': ACCENT, 'muted': MUTED}
    path.write_text(svg, encoding='utf-8')


def main():
    mags = star_magnitudes()
    print('%d stars, magnitudes %.2f to %.2f' % (len(mags), min(mags), max(mags)))
    make_logo(mags, HERE / 'logo.svg')
    make_banner(mags, HERE / 'banner.svg')
    print('Wrote branding/logo.svg and branding/banner.svg')
    return 0


if __name__ == '__main__':
    sys.exit(main())
