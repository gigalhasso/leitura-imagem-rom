from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import extract_card_images as extractor


class CardImageExtractorTests(unittest.TestCase):
    def test_psx_abgr1555_color_channels(self) -> None:
        self.assertEqual(extractor.psx_color(0x1F, 0x00), (255, 0, 0, 255))
        self.assertEqual(extractor.psx_color(0xE0, 0x03), (0, 255, 0, 255))
        self.assertEqual(extractor.psx_color(0x00, 0x7C), (0, 0, 255, 255))

    def test_indexed8_uses_palette_after_pixel_data(self) -> None:
        raw = bytearray(1024)
        raw[:4] = bytes((1, 2, 3, 0))
        raw[512 + 2 : 512 + 4] = bytes((0x1F, 0x00))
        raw[512 + 4 : 512 + 6] = bytes((0xE0, 0x03))
        raw[512 + 6 : 512 + 8] = bytes((0x00, 0x7C))
        image = extractor.decode_indexed8(bytes(raw), 0, 2, 2, 512)
        self.assertEqual(image.getpixel((0, 0)), (255, 0, 0, 255))
        self.assertEqual(image.getpixel((1, 0)), (0, 255, 0, 255))
        self.assertEqual(image.getpixel((0, 1)), (0, 0, 255, 255))

    def test_card_ids_are_one_based_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "WA_MRG.MRG"
            marker_offset = extractor.CARD_REGION_OFFSET + extractor.CARD_RECORD_SIZE
            with path.open("wb") as output:
                output.seek(marker_offset)
                output.write(b"second-card")
                output.seek(marker_offset + extractor.CARD_RECORD_SIZE - 1)
                output.write(b"\0")
            self.assertTrue(extractor.read_record(path, 2).startswith(b"second-card"))


if __name__ == "__main__":
    unittest.main()
