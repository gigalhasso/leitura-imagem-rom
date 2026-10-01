from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from extract_opponent_images import (  # noqa: E402
    PORTRAIT_HEIGHT,
    PORTRAIT_PALETTE_SIZE,
    PORTRAIT_PIXEL_SIZE,
    PORTRAIT_RECORD_SIZE,
    PORTRAIT_WIDTH,
    decode_portrait,
    extract_free_duel_deck_icon,
    extract_opponents,
    extract_portraits,
)


class OpponentImageTests(unittest.TestCase):
    def test_record_layout_is_exact(self) -> None:
        self.assertEqual(PORTRAIT_PIXEL_SIZE, 2304)
        self.assertEqual(PORTRAIT_PALETTE_SIZE, 128)
        self.assertEqual(PORTRAIT_RECORD_SIZE, 2432)

    def test_decode_uses_64_color_palette(self) -> None:
        pixels = bytes([1]) * PORTRAIT_PIXEL_SIZE
        palette = bytearray(PORTRAIT_PALETTE_SIZE)
        palette[2:4] = (0x1F, 0x00)
        image = decode_portrait(pixels + palette)
        self.assertEqual(image.size, (PORTRAIT_WIDTH, PORTRAIT_HEIGHT))
        self.assertEqual(image.getpixel((0, 0)), (255, 0, 0, 255))

    def test_extract_preserves_authoritative_slot_number(self) -> None:
        record = bytes(PORTRAIT_RECORD_SIZE)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "WA_MRG.MRG"
            source.write_bytes(bytes(16_076_800) + record * 40)
            paths = extract_portraits(source, Path(directory) / "out", [1, 40])
            self.assertEqual([path.name for path in paths], ["opponent_01.png", "opponent_40.png"])
            with Image.open(paths[1]) as image:
                self.assertEqual(image.size, (48, 48))

    def test_opponent_mapping_can_skip_reserved_first_slot(self) -> None:
        records = []
        for slot in range(1, 41):
            pixels = bytes([1]) * PORTRAIT_PIXEL_SIZE
            palette = bytearray(PORTRAIT_PALETTE_SIZE)
            palette[2:4] = (slot & 0x1F, 0)
            records.append(pixels + palette)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "WA_MRG.MRG"
            source.write_bytes(bytes(16_076_800) + b"".join(records))
            paths = extract_opponents(source, Path(directory) / "out", first_slot=2)
            self.assertEqual(len(paths), 39)
            with Image.open(paths[0]) as image:
                self.assertEqual(image.getpixel((0, 0))[0], 2 * 255 // 31)

    def test_deck_icon_preserves_reserved_slot_one(self) -> None:
        pixels = bytes([1]) * PORTRAIT_PIXEL_SIZE
        palette = bytearray(PORTRAIT_PALETTE_SIZE)
        palette[2:4] = (0x1F, 0)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "WA_MRG.MRG"
            source.write_bytes(bytes(16_076_800) + (pixels + palette) * 40)
            output = Path(directory) / "menu" / "free_duel_deck.png"
            self.assertEqual(extract_free_duel_deck_icon(source, output), output)
            with Image.open(output) as image:
                self.assertEqual(image.getpixel((0, 0)), (255, 0, 0, 255))


if __name__ == "__main__":
    unittest.main()
