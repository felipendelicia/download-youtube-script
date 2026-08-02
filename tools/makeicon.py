"""Genera icon.ico. Requiere Pillow: pip install pillow ; python3 tools/makeicon.py"""

from PIL import Image, ImageDraw

S = 1024  # se dibuja grande y se reduce con LANCZOS para bordes limpios

TOP = (255, 61, 61)
BOTTOM = (193, 18, 31)
WHITE = (255, 255, 255, 255)


def bezier(p0, p1, p2, steps=60):
    points = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
        y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
        points.append((x, y))
    return points


def background():
    """Squircle con gradiente vertical."""
    gradient = Image.new("RGB", (S, S))
    draw = ImageDraw.Draw(gradient)
    for y in range(S):
        t = y / (S - 1)
        draw.line(
            [(0, y), (S, y)],
            fill=tuple(round(TOP[i] + (BOTTOM[i] - TOP[i]) * t) for i in range(3)),
        )

    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.225), fill=255)

    card = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    card.paste(gradient, (0, 0), mask)
    return card


def note(canvas, cx, cy, scale, stemWidth):
    """Corchea blanca: cabeza inclinada, plica y bandera."""
    headW, headH = 300 * scale, 232 * scale
    stemH = 560 * scale

    head = Image.new("RGBA", (int(headW) + 8, int(headH) + 8), (0, 0, 0, 0))
    ImageDraw.Draw(head).ellipse([4, 4, headW, headH], fill=WHITE)
    head = head.rotate(22, resample=Image.BICUBIC, expand=True)

    headX = int(cx - head.width / 2)
    headY = int(cy + stemH / 2 - head.height / 2)
    canvas.alpha_composite(head, (headX, headY))

    draw = ImageDraw.Draw(canvas)
    stemX = cx + headW / 2 - stemWidth * 0.55
    stemTop = cy - stemH / 2
    stemBottom = cy + stemH / 2 - 10 * scale
    draw.rounded_rectangle(
        [stemX - stemWidth / 2, stemTop, stemX + stemWidth / 2, stemBottom],
        radius=stemWidth / 2,
        fill=WHITE,
    )

    # Bandera: dos beziers que se cierran en una forma llena.
    outer = bezier(
        (stemX, stemTop + 4 * scale),
        (stemX + 300 * scale, stemTop + 60 * scale),
        (stemX + 150 * scale, stemTop + 330 * scale),
    )
    inner = bezier(
        (stemX + 150 * scale, stemTop + 330 * scale),
        (stemX + 190 * scale, stemTop + 90 * scale),
        (stemX, stemTop + 130 * scale),
    )
    draw.polygon(outer + inner, fill=WHITE)


def downloadBadge(canvas, cx, cy, radius):
    """Circulo blanco con flecha hacia abajo, para el 'descargar'."""
    draw = ImageDraw.Draw(canvas)
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=WHITE)

    red = (206, 22, 34, 255)
    shaft = radius * 0.20
    top = cy - radius * 0.52
    mid = cy + radius * 0.02
    draw.rounded_rectangle(
        [cx - shaft, top, cx + shaft, mid], radius=shaft * 0.6, fill=red
    )
    head = radius * 0.46
    draw.polygon(
        [(cx - head, mid - shaft * 0.4), (cx + head, mid - shaft * 0.4), (cx, cy + radius * 0.56)],
        fill=red,
    )


def render(detailed: bool):
    canvas = background()

    if not detailed:
        # Sin badge: a 32px o menos seria una mancha. La nota va mas gruesa.
        # cy compensa que la cabeza cuelga por debajo del centro de la plica.
        note(canvas, cx=S * 0.42, cy=S * 0.42, scale=1.20, stemWidth=95)
        return canvas

    badgeX, badgeY, badgeR = S * 0.735, S * 0.735, S * 0.185
    gap = S * 0.030

    # La nota se dibuja aparte para poder recortarle un anillo alrededor del
    # badge: sin ese hueco las dos formas blancas se leen como una mancha.
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    note(layer, cx=S * 0.38, cy=S * 0.42, scale=0.88, stemWidth=58)
    ImageDraw.Draw(layer).ellipse(
        [badgeX - badgeR - gap, badgeY - badgeR - gap,
         badgeX + badgeR + gap, badgeY + badgeR + gap],
        fill=(0, 0, 0, 0),
    )

    canvas.alpha_composite(layer)
    downloadBadge(canvas, cx=badgeX, cy=badgeY, radius=badgeR)
    return canvas


detailedIcon = render(detailed=True)
simpleIcon = render(detailed=False)




layers = []
for size in (256, 128, 64, 48):
    layers.append(detailedIcon.resize((size, size), Image.LANCZOS))
for size in (32, 24, 16):
    layers.append(simpleIcon.resize((size, size), Image.LANCZOS))

layers[0].save(
    "icon.ico",
    format="ICO",
    sizes=[(im.width, im.height) for im in layers],
    append_images=layers[1:],
)
print("icon.ico escrito")
