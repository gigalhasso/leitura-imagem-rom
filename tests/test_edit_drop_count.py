from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import edit_drop_count as editor


def make_fixture(count: int) -> bytes:
    data = bytearray(editor.REQUIRED_SIZE)
    for group in editor.INJECTION_GROUPS:
        offset = (
            editor.INJECTION_BASE
            + group * editor.INJECTION_STRIDE
            + editor.INJECTION_SIGNATURE_OFFSET
        )
        data[offset : offset + len(editor.INJECTION_SIGNATURE)] = (
            editor.INJECTION_SIGNATURE
        )
    for offset in editor.N_PLUS_ONE_OFFSETS:
        data[offset] = count + 1
    for offset in editor.N_OFFSETS:
        data[offset] = count
    return bytes(data)


class DropCountEditorTests(unittest.TestCase):
    def test_inspects_valid_layout(self) -> None:
        state = editor.inspect_drop_count(make_fixture(15))
        self.assertEqual(state.count, 15)
        self.assertEqual(state.n_offsets, 7)
        self.assertEqual(state.n_plus_one_offsets, 15)

    def test_patch_changes_only_the_22_count_bytes(self) -> None:
        original = make_fixture(5)
        patched, old_state = editor.patch_drop_count(original, 12)

        self.assertEqual(old_state.count, 5)
        self.assertEqual(editor.inspect_drop_count(patched).count, 12)
        changed = {index for index, pair in enumerate(zip(original, patched)) if pair[0] != pair[1]}
        self.assertEqual(changed, set(editor.COUNT_OFFSETS))

    def test_rejects_inconsistent_count_bytes(self) -> None:
        data = bytearray(make_fixture(5))
        data[editor.N_OFFSETS[-1]] = 6
        with self.assertRaisesRegex(editor.DropCountLayoutError, "Inconsistent N bytes"):
            editor.inspect_drop_count(data)

    def test_rejects_missing_injection_signature(self) -> None:
        data = bytearray(make_fixture(5))
        signature_offset = (
            editor.INJECTION_BASE
            + max(editor.INJECTION_GROUPS) * editor.INJECTION_STRIDE
            + editor.INJECTION_SIGNATURE_OFFSET
        )
        data[signature_offset] ^= 0xFF
        with self.assertRaisesRegex(editor.DropCountLayoutError, "signature not found"):
            editor.inspect_drop_count(data)

    def test_write_creates_backup_and_preserves_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "WA_MRG.MRG"
            original = make_fixture(5)
            path.write_bytes(original)

            first, _ = editor.patch_drop_count(original, 10)
            backup, created = editor.write_with_backup(path, first)
            self.assertTrue(created)
            self.assertEqual(backup.read_bytes(), original)
            self.assertEqual(editor.inspect_drop_count(path.read_bytes()).count, 10)

            second, _ = editor.patch_drop_count(path.read_bytes(), 15)
            same_backup, created = editor.write_with_backup(path, second)
            self.assertFalse(created)
            self.assertEqual(same_backup, backup)
            self.assertEqual(backup.read_bytes(), original)
            self.assertEqual(editor.inspect_drop_count(path.read_bytes()).count, 15)

    def test_write_rejects_invalid_existing_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "WA_MRG.MRG"
            original = make_fixture(5)
            path.write_bytes(original)
            backup = pathlib.Path(str(path) + ".drop-count.bak")
            backup.write_bytes(b"not a valid backup")

            patched, _ = editor.patch_drop_count(original, 10)
            with self.assertRaisesRegex(ValueError, "different size"):
                editor.write_with_backup(path, patched)
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
