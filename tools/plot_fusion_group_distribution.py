"""Create a PNG plot for the fusion material-group size distribution."""

import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "exports" / "fusion_patterns" / "distribuicao_tamanho_grupos.csv"
OUTPUT = ROOT / "exports" / "fusion_patterns" / "distribuicao_tamanho_grupos.png"


def font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def main() -> None:
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))

    values = {int(row["tamanho_do_grupo"]): int(row["quantidade_de_grupos"]) for row in rows}
    sizes = list(range(min(values), max(values) + 1))
    counts = [values.get(size, 0) for size in sizes]

    width, height = 1400, 800
    left, top, right, bottom = 105, 85, 45, 105
    plot_width = width - left - right
    plot_height = height - top - bottom
    max_count = max(counts)
    y_step = 25
    y_max = ((max_count + y_step - 1) // y_step) * y_step

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = font(30, bold=True)
    label_font = font(20)
    small_font = font(16)

    draw.text((left, 25), "Distribuicao do tamanho dos grupos de fusao", fill="#172033", font=title_font)
    draw.text((left, 59), "Quantidade de grupos por numero de cartas no conjunto", fill="#526070", font=small_font)

    for tick in range(0, y_max + 1, y_step):
        y = top + plot_height - (tick / y_max) * plot_height
        draw.line((left, y, width - right, y), fill="#e3e8ef", width=1)
        draw.text((left - 48, y - 11), str(tick), fill="#526070", font=small_font)

    draw.line((left, top, left, top + plot_height), fill="#526070", width=2)
    draw.line((left, top + plot_height, width - right, top + plot_height), fill="#526070", width=2)

    def point(size: int, count: int):
        x = left + ((size - sizes[0]) / (sizes[-1] - sizes[0])) * plot_width
        y = top + plot_height - (count / y_max) * plot_height
        return x, y

    points = [point(size, count) for size, count in zip(sizes, counts)]
    draw.line(points, fill="#1f6feb", width=4)
    for (size, count), (x, y) in zip(zip(sizes, counts), points):
        if count:
            radius = 5 if count < 20 else 7
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="#1f6feb", outline="white", width=2)

    for size in [1, 5, 10, 15, 20, 25, 30, 31]:
        if size in values:
            x, y = point(size, values[size])
            draw.text((x - 10, top + plot_height + 15), str(size), fill="#526070", font=small_font)

    draw.text((width // 2 - 100, height - 52), "Tamanho do grupo (cartas)", fill="#172033", font=label_font)
    draw.text((18, top + plot_height // 2 + 80), "Grupos", fill="#172033", font=label_font)
    draw.text((left + 12, top + 10), f"maximo: {max_count}", fill="#1f6feb", font=small_font)

    image.save(OUTPUT, "PNG")
    print(f"Created {OUTPUT}")


if __name__ == "__main__":
    main()
