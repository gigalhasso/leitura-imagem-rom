from __future__ import annotations

import argparse
import csv
import pathlib


def read_u16le(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


def read_table(path: pathlib.Path, offset: int, count: int) -> list[int]:
    data = path.read_bytes()
    end = offset + count * 2
    if end > len(data):
        raise ValueError(f"Table exceeds file size: end=0x{end:X}, size=0x{len(data):X}")
    return [read_u16le(data, offset + index * 2) for index in range(count)]


def write_by_position(path: pathlib.Path, values: list[int], group_size: int, delimiter: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=delimiter)
        writer.writerow(
            [
                "position",
                "byte_offset_from_table_start",
                "raw_u16le_value",
                "hex_u16le_value",
                "group_index",
                "slot_in_group",
                "known_card_name",
                "group_guess",
                "notes",
            ]
        )
        for position, value in enumerate(values):
            writer.writerow(
                [
                    position,
                    position * 2,
                    value,
                    f"0x{value:04X}",
                    position // group_size if group_size else "",
                    position % group_size if group_size else "",
                    "",
                    "",
                    "",
                ]
            )


def write_by_card_id(path: pathlib.Path, values: list[int], group_size: int, delimiter: str) -> None:
    positions_by_value = {value: position for position, value in enumerate(values)}
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=delimiter)
        writer.writerow(
            [
                "card_id_or_value",
                "position_in_table",
                "byte_offset_from_table_start",
                "group_index",
                "slot_in_group",
                "known_card_name",
                "type_guess",
                "attribute_guess",
                "notes",
            ]
        )
        for value in sorted(positions_by_value):
            position = positions_by_value[value]
            writer.writerow(
                [
                    value,
                    position,
                    position * 2,
                    position // group_size if group_size else "",
                    position % group_size if group_size else "",
                    "",
                    "",
                    "",
                    "",
                ]
            )


def write_groups(path: pathlib.Path, values: list[int], group_size: int, delimiter: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=delimiter)
        header = ["group_index", "start_position", "start_byte_offset"]
        for slot in range(group_size):
            header.extend([f"slot_{slot}_value", f"slot_{slot}_known_name", f"slot_{slot}_notes"])
        header.extend(["group_guess", "notes"])
        writer.writerow(header)

        for group_index, start in enumerate(range(0, len(values), group_size)):
            group = values[start : start + group_size]
            row: list[object] = [group_index, start, start * 2]
            for slot in range(group_size):
                row.append(group[slot] if slot < len(group) else "")
                row.append("")
                row.append("")
            row.extend(["", ""])
            writer.writerow(row)


def validate_permutation(values: list[int]) -> str:
    expected = set(range(len(values)))
    actual = set(values)
    if actual == expected and len(actual) == len(values):
        return f"perfect permutation of 0..{len(values) - 1}"
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    duplicates = len(values) - len(actual)
    return f"not a perfect permutation; missing={missing[:20]} extra={extra[:20]} duplicates={duplicates}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a uint16 little-endian table to CSV views.")
    parser.add_argument("input", type=pathlib.Path)
    parser.add_argument("--offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--group-size", type=int, default=3)
    parser.add_argument("--output-dir", type=pathlib.Path, default=pathlib.Path("exports"))
    parser.add_argument("--prefix", default="u16_table")
    parser.add_argument("--delimiter", default=",", help="CSV delimiter. Use ';' for many pt-BR spreadsheets.")
    args = parser.parse_args()

    values = read_table(args.input, args.offset, args.count)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    by_position = args.output_dir / f"{args.prefix}_by_position.csv"
    by_card_id = args.output_dir / f"{args.prefix}_by_card_id.csv"
    groups = args.output_dir / f"{args.prefix}_groups_of_{args.group_size}.csv"

    write_by_position(by_position, values, args.group_size, args.delimiter)
    write_by_card_id(by_card_id, values, args.group_size, args.delimiter)
    write_groups(groups, values, args.group_size, args.delimiter)

    print(f"Read {len(values)} values from {args.input} at 0x{args.offset:08X}")
    print(validate_permutation(values))
    print(f"Wrote {by_position}")
    print(f"Wrote {by_card_id}")
    print(f"Wrote {groups}")


if __name__ == "__main__":
    main()
