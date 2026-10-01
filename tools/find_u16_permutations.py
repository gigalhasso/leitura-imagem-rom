from __future__ import annotations

import argparse
import pathlib


def read_u16le(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


def find_permutations(path: pathlib.Path, max_value: int, alignment_step: int) -> list[int]:
    data = path.read_bytes()
    count = max_value + 1
    wanted = set(range(count))
    wanted_sum = max_value * (max_value + 1) // 2
    wanted_squares = max_value * (max_value + 1) * (2 * max_value + 1) // 6
    hits: list[int] = []

    for alignment in range(0, alignment_step, 2):
        values = [
            read_u16le(data, offset)
            for offset in range(alignment, len(data) - 1, 2)
        ]
        if len(values) < count:
            continue

        window = values[:count]
        current_sum = sum(window)
        current_squares = sum(value * value for value in window)

        for index in range(0, len(values) - count + 1):
            if current_sum == wanted_sum and current_squares == wanted_squares:
                candidate = values[index : index + count]
                if set(candidate) == wanted:
                    hits.append(alignment + index * 2)

            if index + count >= len(values):
                break
            outgoing = values[index]
            incoming = values[index + count]
            current_sum += incoming - outgoing
            current_squares += incoming * incoming - outgoing * outgoing
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description="Find contiguous uint16 little-endian permutations.")
    parser.add_argument("paths", nargs="+", type=pathlib.Path)
    parser.add_argument("--max-value", type=int, default=722)
    parser.add_argument("--alignment-step", type=int, default=2)
    parser.add_argument("--sample-count", type=int, default=24)
    args = parser.parse_args()

    files: list[pathlib.Path] = []
    for path in args.paths:
        if path.is_dir():
            files.extend(p for p in path.rglob("*") if p.is_file())
        else:
            files.append(path)

    for file_path in files:
        data = file_path.read_bytes()
        for offset in find_permutations(file_path, args.max_value, args.alignment_step):
            values = [read_u16le(data, offset + index * 2) for index in range(args.max_value + 1)]
            sample = ", ".join(str(value) for value in values[: args.sample_count])
            print(f"{file_path}\toffset=0x{offset:08X}\tcount={len(values)}\tsample=[{sample}]")


if __name__ == "__main__":
    main()
