from __future__ import annotations

import argparse
import pathlib


KNOWN_ATK_DEF = [
    (1, 3000, 2500),  # Blue Eyes White Dragon
    (2, 800, 2000),   # Mystical Elf
    (3, 1200, 1000),  # Hitotsu-Me Giant
    (4, 1200, 700),   # Baby Dragon
    (5, 1000, 500),   # Ryu-Kishin
    (6, 1300, 1400),  # Feral Imp
    (7, 1400, 1200),  # Winged Dragon #1
    (8, 800, 600),    # Mushroom Man
    (9, 500, 200),    # Shadow Specter
    (10, 1500, 800),  # Blackland Fire Dragon
]


def u16le(value: int) -> bytes:
    return value.to_bytes(2, "little")


def build_pattern(mode: str) -> bytes:
    chunks: list[bytes] = []
    for _card_id, attack, defense in KNOWN_ATK_DEF:
        if mode == "atkdef":
            chunks.append(u16le(attack) + u16le(defense))
        elif mode == "id-atkdef":
            chunks.append(u16le(_card_id) + u16le(attack) + u16le(defense))
        else:
            raise ValueError(mode)
    return b"".join(chunks)


def find_pattern(data: bytes, pattern: bytes) -> list[int]:
    hits: list[int] = []
    start = 0
    while True:
        hit = data.find(pattern, start)
        if hit == -1:
            return hits
        hits.append(hit)
        start = hit + 1


def fuzzy_record_hits(data: bytes, record_size: int, min_matches: int) -> list[tuple[int, int]]:
    hits: list[tuple[int, int]] = []
    max_start = len(data) - len(KNOWN_ATK_DEF) * record_size
    for offset in range(0, max_start + 1, 2):
        matches = 0
        for index, (_card_id, attack, defense) in enumerate(KNOWN_ATK_DEF):
            record_offset = offset + index * record_size
            record = data[record_offset : record_offset + record_size]
            if u16le(attack) in record and u16le(defense) in record:
                matches += 1
        if matches >= min_matches:
            hits.append((offset, matches))
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description="Search known early card ATK/DEF values in binaries.")
    parser.add_argument("paths", nargs="+", type=pathlib.Path)
    parser.add_argument("--record-sizes", default="4,6,8,10,12,16,20,24,32")
    parser.add_argument("--min-matches", type=int, default=8)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--exact-only", action="store_true")
    args = parser.parse_args()

    files: list[pathlib.Path] = []
    for path in args.paths:
        if path.is_dir():
            files.extend(p for p in path.rglob("*") if p.is_file())
        else:
            files.append(path)

    for file_path in files:
        data = file_path.read_bytes()
        for mode in ("atkdef", "id-atkdef"):
            for hit in find_pattern(data, build_pattern(mode)):
                print(f"{file_path}\tmode={mode}\texact_offset=0x{hit:08X}")

        if args.exact_only:
            continue

        shown = 0
        for record_size in [int(value) for value in args.record_sizes.split(",") if value]:
            for offset, matches in fuzzy_record_hits(data, record_size, args.min_matches):
                print(f"{file_path}\trec={record_size}\tfuzzy_offset=0x{offset:08X}\tmatches={matches}")
                shown += 1
                if shown >= args.limit:
                    break
            if shown >= args.limit:
                break


if __name__ == "__main__":
    main()
