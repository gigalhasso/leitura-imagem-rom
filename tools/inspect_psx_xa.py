from __future__ import annotations

import argparse
import collections
import pathlib


RAW_SECTOR_SIZE = 2352
XA_SUBHEADER_OFFSET = 16


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory Mode 2 XA subchannels in a raw PS1 BIN.")
    parser.add_argument("image", type=pathlib.Path)
    parser.add_argument("start_lba", type=lambda value: int(value, 0))
    parser.add_argument("--count", type=lambda value: int(value, 0))
    args = parser.parse_args()

    total_sectors = args.image.stat().st_size // RAW_SECTOR_SIZE
    count = args.count if args.count is not None else total_sectors - args.start_lba
    count = min(count, total_sectors - args.start_lba)

    counts: collections.Counter[tuple[int, int, int, int]] = collections.Counter()
    first_lba: dict[tuple[int, int, int, int], int] = {}

    with args.image.open("rb") as source:
        source.seek(args.start_lba * RAW_SECTOR_SIZE)
        for relative_lba in range(count):
            sector = source.read(RAW_SECTOR_SIZE)
            if len(sector) != RAW_SECTOR_SIZE:
                break
            key = tuple(sector[XA_SUBHEADER_OFFSET : XA_SUBHEADER_OFFSET + 4])
            counts[key] += 1
            first_lba.setdefault(key, args.start_lba + relative_lba)

    print(f"start_lba={args.start_lba} sectors={sum(counts.values())}")
    print("file channel submode coding sectors first_lba")
    for key, sector_count in counts.most_common():
        file_number, channel, submode, coding = key
        print(
            f"{file_number:4d} {channel:7d} 0x{submode:02X}    0x{coding:02X} "
            f"{sector_count:7d} {first_lba[key]:9d}"
        )


if __name__ == "__main__":
    main()
