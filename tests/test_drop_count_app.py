from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import edit_drop_count as editor
from drop_count_app import add_drop_suffix, inspect_input, resolve_cue, save_drop_count


def make_wa_fixture(count: int) -> bytes:
    data = bytearray(editor.REQUIRED_SIZE)
    for group in editor.INJECTION_GROUPS:
        offset = (
            editor.INJECTION_BASE
            + group * editor.INJECTION_STRIDE
            + editor.INJECTION_SIGNATURE_OFFSET
        )
        data[offset : offset + len(editor.INJECTION_SIGNATURE)] = editor.INJECTION_SIGNATURE
    for offset in editor.N_PLUS_ONE_OFFSETS:
        data[offset] = count + 1
    for offset in editor.N_OFFSETS:
        data[offset] = count
    return bytes(data)


class DropCountAppTests(unittest.TestCase):
    def test_adds_and_replaces_drop_suffix(self) -> None:
        self.assertEqual(
            add_drop_suffix(pathlib.Path("Game.iso"), 15).name,
            "Game (Drop x15).iso",
        )
        self.assertEqual(
            add_drop_suffix(pathlib.Path("Game (Drop x5).bin"), 1).name,
            "Game (Drop x1).bin",
        )

    def test_resolves_quoted_cue_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            image = root / "My Game.bin"
            image.write_bytes(b"image")
            cue = root / "My Game.cue"
            cue.write_text('FILE "My Game.bin" BINARY\n  TRACK 01 MODE2/2352\n')
            self.assertEqual(resolve_cue(cue), image.resolve())

    def test_rejects_multifile_cue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            cue = root / "multi.cue"
            cue.write_text('FILE "a.bin" BINARY\nFILE "b.bin" BINARY\n')
            with self.assertRaisesRegex(ValueError, "exatamente uma"):
                resolve_cue(cue)

    def test_saves_wa_as_copy_without_changing_original(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            original = root / "WA_MRG.MRG"
            destination = root / "WA_MRG (Drop x15).MRG"
            original.write_bytes(make_wa_fixture(5))

            result = save_drop_count(inspect_input(original), 15, "copy", destination)

            self.assertEqual(result.output_path, destination.resolve())
            self.assertEqual(result.changed_bytes, 22)
            self.assertEqual(inspect_input(original).current_count, 5)
            self.assertEqual(inspect_input(destination).current_count, 15)

    def test_replaces_wa_and_keeps_original_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original = pathlib.Path(directory) / "WA_MRG.MRG"
            original.write_bytes(make_wa_fixture(5))

            result = save_drop_count(inspect_input(original), 1, "replace")

            self.assertIsNotNone(result.backup_path)
            self.assertEqual(inspect_input(original).current_count, 1)
            self.assertEqual(inspect_input(result.backup_path).current_count, 5)


if __name__ == "__main__":
    unittest.main()
