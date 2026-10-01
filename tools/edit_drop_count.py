from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import tempfile
from dataclasses import dataclass


MIN_DROP_COUNT = 1
MAX_DROP_COUNT = 15

INJECTION_BASE = 0x00B4C400
INJECTION_STRIDE = 0x00075800
INJECTION_GROUPS = range(1, 8)
INJECTION_SIGNATURE_OFFSET = 0x40
INJECTION_SIGNATURE = bytes.fromhex("1B001D3C00ACBD27")

N_PLUS_ONE_OFFSETS = (
    0x00BC17E4,
    *(INJECTION_BASE + group * INJECTION_STRIDE + 0x78 for group in INJECTION_GROUPS),
    *(INJECTION_BASE + group * INJECTION_STRIDE + 0x174 for group in INJECTION_GROUPS),
)
N_OFFSETS = tuple(
    INJECTION_BASE + group * INJECTION_STRIDE + 0x1EC
    for group in INJECTION_GROUPS
)
COUNT_OFFSETS = (*N_PLUS_ONE_OFFSETS, *N_OFFSETS)
REQUIRED_SIZE = max(
    max(COUNT_OFFSETS) + 1,
    INJECTION_BASE
    + max(INJECTION_GROUPS) * INJECTION_STRIDE
    + INJECTION_SIGNATURE_OFFSET
    + len(INJECTION_SIGNATURE),
)


class DropCountLayoutError(ValueError):
    """Raised when a WA_MRG.MRG does not have a consistent Ghost patch layout."""


@dataclass(frozen=True)
class DropCountState:
    count: int
    n_offsets: int = len(N_OFFSETS)
    n_plus_one_offsets: int = len(N_PLUS_ONE_OFFSETS)


def _format_observed(data: bytes, offsets: tuple[int, ...]) -> str:
    grouped: dict[int, list[int]] = {}
    for offset in offsets:
        grouped.setdefault(data[offset], []).append(offset)
    return "; ".join(
        f"0x{value:02X} at " + ", ".join(f"0x{offset:08X}" for offset in positions)
        for value, positions in sorted(grouped.items())
    )


def inspect_drop_count(data: bytes) -> DropCountState:
    if len(data) < REQUIRED_SIZE:
        raise DropCountLayoutError(
            f"File is too small for the Ghost multi-drop layout: "
            f"size=0x{len(data):X}, required>=0x{REQUIRED_SIZE:X}"
        )

    for group in INJECTION_GROUPS:
        offset = (
            INJECTION_BASE
            + group * INJECTION_STRIDE
            + INJECTION_SIGNATURE_OFFSET
        )
        observed = data[offset : offset + len(INJECTION_SIGNATURE)]
        if observed != INJECTION_SIGNATURE:
            raise DropCountLayoutError(
                f"Ghost injection signature not found in group {group} at "
                f"0x{offset:08X}: expected={INJECTION_SIGNATURE.hex().upper()}, "
                f"observed={observed.hex().upper()}"
            )

    n_values = {data[offset] for offset in N_OFFSETS}
    if len(n_values) != 1:
        raise DropCountLayoutError(
            "Inconsistent N bytes: " + _format_observed(data, N_OFFSETS)
        )
    count = next(iter(n_values))
    if not MIN_DROP_COUNT <= count <= MAX_DROP_COUNT:
        raise DropCountLayoutError(
            f"Invalid drop count {count}; expected {MIN_DROP_COUNT}..{MAX_DROP_COUNT}"
        )

    expected_limit = count + 1
    limit_values = {data[offset] for offset in N_PLUS_ONE_OFFSETS}
    if limit_values != {expected_limit}:
        raise DropCountLayoutError(
            f"Inconsistent N+1 bytes for N={count}; expected 0x{expected_limit:02X}: "
            + _format_observed(data, N_PLUS_ONE_OFFSETS)
        )

    return DropCountState(count=count)


def patch_drop_count(data: bytes, new_count: int) -> tuple[bytes, DropCountState]:
    if not MIN_DROP_COUNT <= new_count <= MAX_DROP_COUNT:
        raise ValueError(
            f"Drop count must be between {MIN_DROP_COUNT} and {MAX_DROP_COUNT}"
        )

    old_state = inspect_drop_count(data)
    patched = bytearray(data)
    for offset in N_PLUS_ONE_OFFSETS:
        patched[offset] = new_count + 1
    for offset in N_OFFSETS:
        patched[offset] = new_count

    new_state = inspect_drop_count(patched)
    if new_state.count != new_count:
        raise AssertionError("Patched data did not pass its own validation")
    return bytes(patched), old_state


def _default_backup_path(path: pathlib.Path) -> pathlib.Path:
    return path.with_name(path.name + ".drop-count.bak")


def write_atomically(path: pathlib.Path, data: bytes) -> None:
    temporary_path: pathlib.Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=path.name + ".", suffix=".tmp", dir=path.parent, delete=False
        ) as output:
            temporary_path = pathlib.Path(output.name)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def write_with_backup(
    path: pathlib.Path, data: bytes, backup_path: pathlib.Path | None = None
) -> tuple[pathlib.Path, bool]:
    path = path.resolve()
    backup_path = (backup_path or _default_backup_path(path)).resolve()
    if backup_path == path:
        raise ValueError("Backup path must differ from the WA_MRG.MRG path")

    backup_created = False
    if backup_path.exists():
        if not backup_path.is_file():
            raise ValueError(f"Backup path is not a file: {backup_path}")
        backup_data = backup_path.read_bytes()
        if len(backup_data) != len(data):
            raise ValueError(
                f"Existing backup has a different size: backup=0x{len(backup_data):X}, "
                f"new_file=0x{len(data):X}"
            )
        try:
            inspect_drop_count(backup_data)
        except DropCountLayoutError as error:
            raise ValueError(f"Existing backup is not a valid Ghost layout: {error}") from error
    else:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)
        backup_created = True

    write_atomically(path, data)
    return backup_path, backup_created


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect or safely edit the Ghost multi-card drop count in WA_MRG.MRG. "
            "Without --write, setting a count is only a dry run."
        )
    )
    parser.add_argument("wa_mrg", type=pathlib.Path)
    parser.add_argument(
        "count",
        nargs="?",
        type=int,
        help=f"new card count ({MIN_DROP_COUNT}..{MAX_DROP_COUNT}); omit to inspect",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the validated change; otherwise perform a dry run",
    )
    parser.add_argument(
        "--backup",
        type=pathlib.Path,
        help="backup path (default: WA_MRG.MRG.drop-count.bak)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.write and args.count is None:
        raise SystemExit("error: --write requires a new count")

    try:
        original = args.wa_mrg.read_bytes()
        state = inspect_drop_count(original)
        print(f"Compatible Ghost multi-drop layout: yes")
        print(f"Current cards per duel: {state.count}")
        print(
            f"Validated count bytes: {state.n_offsets} x N, "
            f"{state.n_plus_one_offsets} x (N+1)"
        )

        if args.count is None:
            return

        patched, _ = patch_drop_count(original, args.count)
        changed_offsets = sum(a != b for a, b in zip(original, patched))
        print(f"Requested cards per duel: {args.count}")
        print(f"Bytes that change: {changed_offsets}")
        if not args.write:
            print("Dry run only; file was not changed. Add --write to save.")
            return

        backup_path, backup_created = write_with_backup(
            args.wa_mrg, patched, args.backup
        )
        saved_state = inspect_drop_count(args.wa_mrg.read_bytes())
        if saved_state.count != args.count:
            raise RuntimeError(
                f"Post-write verification failed; backup is at {backup_path}"
            )
        backup_status = "created" if backup_created else "preserved existing"
        print(f"Saved and verified: {args.wa_mrg.resolve()}")
        print(f"Backup ({backup_status}): {backup_path}")
    except (OSError, ValueError, DropCountLayoutError) as error:
        raise SystemExit(f"error: {error}") from error


if __name__ == "__main__":
    main()
