from __future__ import annotations

import argparse
import pathlib

from PIL import Image, ImageDraw


def render(data: bytes, offset: int, width: int, rows: int, bits_per_pixel: int) -> Image.Image:
    if bits_per_pixel == 16:
        byte_count = width * rows * 2
    elif bits_per_pixel == 8:
        byte_count = width * rows
    else:
        byte_count = width * rows // 2
    source = data[offset : offset + byte_count]
    if len(source) != byte_count:
        raise ValueError("requested image exceeds input")
    if bits_per_pixel == 16:
        pixels = bytearray()
        for low, high in zip(source[0::2], source[1::2]):
            value = low | high << 8
            red = (value & 0x1F) * 255 // 31
            green = ((value >> 5) & 0x1F) * 255 // 31
            blue = ((value >> 10) & 0x1F) * 255 // 31
            pixels.extend((red, green, blue))
        image = Image.frombytes("RGB", (width, rows), bytes(pixels))
        return image.resize((width * 2, rows * 2), Image.Resampling.NEAREST)
    if bits_per_pixel == 8:
        pixels = source
    else:
        pixels = bytes(component for value in source for component in (value & 0x0F, value >> 4))
        pixels = bytes(component * 17 for component in pixels)
    image = Image.frombytes("L", (width, rows), pixels)
    return image.resize((width * 2, rows * 2), Image.Resampling.NEAREST)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render raw 8-bit data in several candidate widths.")
    parser.add_argument("input", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument("--offset", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--rows", type=int, default=128)
    parser.add_argument("--widths", type=int, nargs="+", default=[64, 128, 256, 512])
    parser.add_argument("--bpp", choices=(4, 8, 16), type=int, default=8)
    args = parser.parse_args()

    data = args.input.read_bytes()
    panels = [render(data, args.offset, width, args.rows, args.bpp) for width in args.widths]
    canvas_width = max(panel.width for panel in panels)
    canvas_height = sum(panel.height + 28 for panel in panels)
    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")
    draw = ImageDraw.Draw(canvas)
    y = 0
    for width, panel in zip(args.widths, panels):
        draw.text((4, y + 4), f"offset 0x{args.offset:X}; raw {args.bpp}-bit; width {width}", fill="black")
        canvas.paste(panel.convert("RGB"), (0, y + 28))
        y += panel.height + 28
    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output)


if __name__ == "__main__":
    main()
