from __future__ import annotations

import argparse
import pathlib
import struct


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find long aligned runs of ascending little-endian offsets."
    )
    parser.add_argument("input", type=pathlib.Path)
    parser.add_argument("--width", choices=(2, 4), type=int, default=4)
    parser.add_argument("--min-count", type=int, default=500)
    parser.add_argument("--max-step", type=lambda value: int(value, 0), default=0x400000)
    args = parser.parse_args()

    data = args.input.read_bytes()
    unpack = "<H" if args.width == 2 else "<I"
    limit = len(data) - args.width
    results: list[tuple[int, int, int, int]] = []

    for alignment in range(args.width):
        start = alignment
        previous = struct.unpack_from(unpack, data, start)[0]
        count = 1
        for offset in range(start + args.width, limit + 1, args.width):
            current = struct.unpack_from(unpack, data, offset)[0]
            if previous < current and current - previous <= args.max_step:
                count += 1
            else:
                if count >= args.min_count:
                    results.append((start, count, previous, offset - args.width))
                start = offset
                count = 1
            previous = current
        if count >= args.min_count:
            results.append((start, count, previous, limit - (limit - start) % args.width))

    print(f"input={args.input}")
    print(f"width={args.width} min_count={args.min_count} candidates={len(results)}")
    for start, count, last_value, end in results:
        first_value = struct.unpack_from(unpack, data, start)[0]
        print(
            f"start=0x{start:08X} end=0x{end:08X} count={count} "
            f"first=0x{first_value:X} last=0x{last_value:X}"
        )


if __name__ == "__main__":
    main()
