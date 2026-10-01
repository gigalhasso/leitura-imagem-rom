from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


CARD_COUNT = 722
CARD_REGION_OFFSET = 1_478_656  # 0x169000
CARD_RECORD_SIZE = 14_336       # 0x3800

FULL_WIDTH = 102
FULL_HEIGHT = 96
FULL_DATA_SIZE = FULL_WIDTH * FULL_HEIGHT
FULL_PALETTE_OFFSET = FULL_DATA_SIZE

NAME_OFFSET = FULL_DATA_SIZE + 512
NAME_WIDTH = 96
NAME_HEIGHT = 14
NAME_DATA_SIZE = NAME_WIDTH * NAME_HEIGHT // 2

MINI_OFFSET = NAME_OFFSET + NAME_DATA_SIZE
MINI_WIDTH = 40
MINI_HEIGHT = 32
MINI_DATA_SIZE = MINI_WIDTH * MINI_HEIGHT
MINI_PALETTE_OFFSET = MINI_OFFSET + MINI_DATA_SIZE


def psx_color(low: int, high: int) -> tuple[int, int, int, int]:
    """Decode little-endian PS1 ABGR1555 into 8-bit RGBA."""
    value = low | high << 8
    red = (value & 0x1F) * 255 // 31
    green = ((value >> 5) & 0x1F) * 255 // 31
    blue = ((value >> 10) & 0x1F) * 255 // 31
    return red, green, blue, 255


def decode_palette(raw: bytes, offset: int, colors: int = 256) -> list[tuple[int, int, int, int]]:
    palette_bytes = raw[offset : offset + colors * 2]
    if len(palette_bytes) != colors * 2:
        raise ValueError("palette exceeds card record")
    return [psx_color(palette_bytes[i], palette_bytes[i + 1]) for i in range(0, len(palette_bytes), 2)]


def decode_indexed8(raw: bytes, data_offset: int, width: int, height: int, palette_offset: int) -> Image.Image:
    indexes = raw[data_offset : data_offset + width * height]
    if len(indexes) != width * height:
        raise ValueError("pixel data exceeds card record")
    palette = decode_palette(raw, palette_offset)
    rgba = bytes(component for index in indexes for component in palette[index])
    return Image.frombytes("RGBA", (width, height), rgba)


def decode_name(raw: bytes) -> Image.Image:
    packed = raw[NAME_OFFSET : NAME_OFFSET + NAME_DATA_SIZE]
    if len(packed) != NAME_DATA_SIZE:
        raise ValueError("card-name data exceeds card record")
    levels = [255, 0, 32, 64, 96, 128, 160, 192] + [0] * 8
    pixels = bytearray()
    for value in packed:
        for nibble in (value & 0x0F, value >> 4):
            shade = levels[nibble]
            pixels.extend((shade, shade, shade, 255))
    return Image.frombytes("RGBA", (NAME_WIDTH, NAME_HEIGHT), bytes(pixels))


def read_record(wa_mrg: Path, card_id: int) -> bytes:
    if not 1 <= card_id <= CARD_COUNT:
        raise ValueError(f"card ID must be between 1 and {CARD_COUNT}")
    offset = CARD_REGION_OFFSET + (card_id - 1) * CARD_RECORD_SIZE
    with wa_mrg.open("rb") as source:
        source.seek(offset)
        raw = source.read(CARD_RECORD_SIZE)
    if len(raw) != CARD_RECORD_SIZE:
        raise ValueError(f"{wa_mrg} is too small for card {card_id}")
    return raw


def extract_card(wa_mrg: Path, output_dir: Path, card_id: int, kind: str) -> list[Path]:
    raw = read_record(wa_mrg, card_id)
    images: dict[str, Image.Image] = {
        "full": decode_indexed8(raw, 0, FULL_WIDTH, FULL_HEIGHT, FULL_PALETTE_OFFSET),
        "mini": decode_indexed8(raw, MINI_OFFSET, MINI_WIDTH, MINI_HEIGHT, MINI_PALETTE_OFFSET),
        "name": decode_name(raw),
    }
    selected = images if kind == "all" else {kind: images[kind]}
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for image_kind, image in selected.items():
        path = output_dir / f"card_{card_id:03d}_{image_kind}.png"
        image.save(path)
        paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract card graphics from Yu-Gi-Oh! FM WA_MRG.MRG files.")
    parser.add_argument("input", type=Path, help="Path to WA_MRG.MRG")
    parser.add_argument("output", type=Path, help="Output directory")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--card-id", type=int, action="append", help="Card ID (1-722); repeat as needed")
    selection.add_argument("--all-cards", action="store_true", help="Extract all 722 card records")
    parser.add_argument("--kind", choices=("full", "mini", "name", "all"), default="all")
    args = parser.parse_args()

    card_ids = range(1, CARD_COUNT + 1) if args.all_cards else args.card_id
    for card_id in card_ids:
        for path in extract_card(args.input, args.output, card_id, args.kind):
            print(path)


if __name__ == "__main__":
    main()
