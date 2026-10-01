from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


PORTRAIT_COUNT = 40
PORTRAIT_REGION_OFFSET = 16_076_800  # 0x00F55000
PORTRAIT_WIDTH = 48
PORTRAIT_HEIGHT = 48
PORTRAIT_PIXEL_SIZE = PORTRAIT_WIDTH * PORTRAIT_HEIGHT
PORTRAIT_PALETTE_COLORS = 64
PORTRAIT_PALETTE_SIZE = PORTRAIT_PALETTE_COLORS * 2
PORTRAIT_RECORD_SIZE = PORTRAIT_PIXEL_SIZE + PORTRAIT_PALETTE_SIZE  # 0x980


def psx_color(low: int, high: int) -> tuple[int, int, int, int]:
    """Decode little-endian PS1 ABGR1555 into 8-bit RGBA."""
    value = low | high << 8
    red = (value & 0x1F) * 255 // 31
    green = ((value >> 5) & 0x1F) * 255 // 31
    blue = ((value >> 10) & 0x1F) * 255 // 31
    alpha = 0 if value == 0 else 255
    return red, green, blue, alpha


def read_portrait(wa_mrg: Path, slot: int) -> bytes:
    if not 1 <= slot <= PORTRAIT_COUNT:
        raise ValueError(f"portrait slot must be between 1 and {PORTRAIT_COUNT}")
    offset = PORTRAIT_REGION_OFFSET + (slot - 1) * PORTRAIT_RECORD_SIZE
    with wa_mrg.open("rb") as source:
        source.seek(offset)
        raw = source.read(PORTRAIT_RECORD_SIZE)
    if len(raw) != PORTRAIT_RECORD_SIZE:
        raise ValueError(f"{wa_mrg} is too small for portrait slot {slot}")
    return raw


def decode_portrait(raw: bytes) -> Image.Image:
    indexes = raw[:PORTRAIT_PIXEL_SIZE]
    palette_raw = raw[PORTRAIT_PIXEL_SIZE:]
    palette = [
        psx_color(palette_raw[index], palette_raw[index + 1])
        for index in range(0, PORTRAIT_PALETTE_SIZE, 2)
    ]
    rgba = bytes(component for index in indexes for component in palette[index])
    return Image.frombytes("RGBA", (PORTRAIT_WIDTH, PORTRAIT_HEIGHT), rgba)


def extract_portraits(wa_mrg: Path, output_dir: Path, slots: list[int]) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for slot in slots:
        image = decode_portrait(read_portrait(wa_mrg, slot))
        path = output_dir / f"opponent_{slot:02d}.png"
        image.save(path)
        paths.append(path)
    return paths


def extract_opponents(
    wa_mrg: Path, output_dir: Path, first_slot: int, opponent_count: int = 39
) -> list[Path]:
    last_slot = first_slot + opponent_count - 1
    if first_slot < 1 or last_slot > PORTRAIT_COUNT:
        raise ValueError(
            f"opponent mapping needs slots {first_slot}-{last_slot}, "
            f"but only 1-{PORTRAIT_COUNT} exist"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for opponent_id, slot in enumerate(range(first_slot, last_slot + 1), start=1):
        image = decode_portrait(read_portrait(wa_mrg, slot))
        path = output_dir / f"opponent_{opponent_id:02d}.png"
        image.save(path)
        paths.append(path)
    return paths


def extract_free_duel_deck_icon(wa_mrg: Path, output: Path) -> Path:
    """Preserve raw slot 1, the Free Duel deck-menu icon, outside opponent IDs."""
    output.parent.mkdir(parents=True, exist_ok=True)
    decode_portrait(read_portrait(wa_mrg, 1)).save(output)
    return output


def write_contact_sheet(paths: list[Path], output: Path) -> None:
    scale = 3
    cell_width = PORTRAIT_WIDTH * scale + 16
    cell_height = PORTRAIT_HEIGHT * scale + 32
    columns = 8
    rows = (len(paths) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), "#17130d")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGBA").resize(
            (PORTRAIT_WIDTH * scale, PORTRAIT_HEIGHT * scale), Image.Resampling.NEAREST
        )
        x = index % columns * cell_width + 8
        y = index // columns * cell_height + 8
        sheet.paste(image, (x, y), image)
        draw.text((x, y + PORTRAIT_HEIGHT * scale + 4), f"slot {index + 1:02d}", fill="#f0d58b")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract Forbidden Memories opponent-selection portraits from WA_MRG.MRG."
    )
    parser.add_argument("input", type=Path, help="Path to WA_MRG.MRG")
    parser.add_argument("output", type=Path, help="Output directory")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--slot", type=int, action="append", help="Portrait slot (1-40); repeat as needed")
    selection.add_argument("--all", action="store_true", help="Extract all 40 portrait slots")
    selection.add_argument(
        "--opponents",
        action="store_true",
        help="Extract 39 website-ready images named by opponent ID",
    )
    parser.add_argument(
        "--first-slot",
        type=int,
        default=2,
        help="First portrait slot used by opponent ID 1 with --opponents (default: 2)",
    )
    parser.add_argument(
        "--deck-icon-output",
        type=Path,
        help="Also preserve raw slot 1 as the unused Free Duel deck-menu icon",
    )
    parser.add_argument("--contact-sheet", type=Path, help="Also write a numbered contact sheet")
    args = parser.parse_args()

    if args.opponents:
        paths = extract_opponents(args.input, args.output, args.first_slot)
    else:
        slots = list(range(1, PORTRAIT_COUNT + 1)) if args.all else args.slot
        paths = extract_portraits(args.input, args.output, slots)
    if args.contact_sheet:
        write_contact_sheet(paths, args.contact_sheet)
    if args.deck_icon_output:
        print(extract_free_duel_deck_icon(args.input, args.deck_icon_output))
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
