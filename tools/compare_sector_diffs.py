from __future__ import annotations

import argparse
import pathlib


def compare_sectors(
    left: pathlib.Path, right: pathlib.Path, sector_size: int
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    runs: list[tuple[int, int]] = []
    changes: list[tuple[int, int]] = []
    sector_index = 0

    with left.open("rb") as left_file, right.open("rb") as right_file:
        while True:
            left_sector = left_file.read(sector_size)
            right_sector = right_file.read(sector_size)
            if not left_sector and not right_sector:
                break

            if left_sector != right_sector:
                changed_bytes = sum(
                    left_byte != right_byte for left_byte, right_byte in zip(left_sector, right_sector)
                ) + abs(len(left_sector) - len(right_sector))
                changes.append((sector_index, changed_bytes))
                if runs and sector_index == runs[-1][1] + 1:
                    runs[-1] = (runs[-1][0], sector_index)
                else:
                    runs.append((sector_index, sector_index))
            sector_index += 1

    return runs, changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two files as fixed-size sectors.")
    parser.add_argument("base", type=pathlib.Path)
    parser.add_argument("mod", type=pathlib.Path)
    parser.add_argument("--sector-size", type=lambda value: int(value, 0), default=0x800)
    parser.add_argument("--top", type=int, default=0, help="Show sectors with the most changed bytes.")
    args = parser.parse_args()

    runs, changes = compare_sectors(args.base, args.mod, args.sector_size)
    changed_count = sum(end - start + 1 for start, end in runs)
    print(f"base_bytes={args.base.stat().st_size}")
    print(f"mod_bytes={args.mod.stat().st_size}")
    print(f"sector_size={args.sector_size}")
    print(f"changed_sectors={changed_count}")
    print(f"changed_runs={len(runs)}")
    for start, end in runs:
        print(f"sector={start}-{end}\tbytes=0x{start * args.sector_size:X}-0x{(end + 1) * args.sector_size - 1:X}")
    if args.top:
        print("top_changed_sectors")
        for sector, changed_bytes in sorted(changes, key=lambda item: item[1], reverse=True)[: args.top]:
            print(f"sector={sector}\tchanged_bytes={changed_bytes}\tchanged_ratio={changed_bytes / args.sector_size:.3f}")


if __name__ == "__main__":
    main()
