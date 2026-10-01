from __future__ import annotations

import argparse
import dataclasses
import pathlib
import statistics


@dataclasses.dataclass(frozen=True)
class Hit:
    path: pathlib.Path
    offset: int
    record_size: int
    fields: int
    count: int
    score: float
    sample: tuple[tuple[int, ...], ...]


def read_u16le(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


def record_at(data: bytes, offset: int, fields: int) -> tuple[int, ...] | None:
    end = offset + fields * 2
    if end > len(data):
        return None
    return tuple(read_u16le(data, offset + i * 2) for i in range(fields))


def plausible_record(record: tuple[int, ...], max_card_id: int) -> bool:
    non_zero = [value for value in record if value != 0]
    if len(non_zero) < 2:
        return False
    if any(value > max_card_id for value in non_zero):
        return False
    return True


def score_records(records: list[tuple[int, ...]], max_card_id: int) -> float:
    values = [value for record in records for value in record if value != 0]
    unique_ratio = len(set(values)) / max(1, len(values))
    in_range_ratio = sum(1 for value in values if 1 <= value <= max_card_id) / max(1, len(values))
    # Penalize long runs of the exact same record; tables usually vary.
    repeated_adjacent = sum(1 for a, b in zip(records, records[1:]) if a == b)
    repeat_penalty = repeated_adjacent / max(1, len(records) - 1)
    return (in_range_ratio * 0.55) + (unique_ratio * 0.45) - (repeat_penalty * 0.35)


def find_runs(
    path: pathlib.Path,
    min_records: int,
    max_card_id: int,
    record_sizes: list[int],
    fields_options: list[int],
) -> list[Hit]:
    data = path.read_bytes()
    hits: list[Hit] = []

    for fields in fields_options:
        natural_size = fields * 2
        for record_size in record_sizes:
            if record_size < natural_size:
                continue
            for alignment in range(0, min(record_size, 8), 2):
                offset = alignment
                while offset + natural_size <= len(data):
                    records: list[tuple[int, ...]] = []
                    run_start = offset
                    while offset + natural_size <= len(data):
                        record = record_at(data, offset, fields)
                        if record is None or not plausible_record(record, max_card_id):
                            break
                        records.append(record)
                        offset += record_size

                    if len(records) >= min_records:
                        sample = tuple(records[:8])
                        hits.append(
                            Hit(
                                path=path,
                                offset=run_start,
                                record_size=record_size,
                                fields=fields,
                                count=len(records),
                                score=score_records(records, max_card_id),
                                sample=sample,
                            )
                        )
                    if records:
                        offset = max(offset, run_start + len(records) * record_size)
                    else:
                        offset = run_start + record_size

    return hits


def collapse_overlapping(hits: list[Hit]) -> list[Hit]:
    by_key: dict[tuple[pathlib.Path, int, int], Hit] = {}
    for hit in sorted(hits, key=lambda h: (h.path, h.record_size, h.fields, h.offset)):
        key = (hit.path, hit.record_size, hit.fields)
        previous = by_key.get(key)
        if previous and hit.offset < previous.offset + previous.count * previous.record_size:
            if (hit.count, hit.score) > (previous.count, previous.score):
                by_key[key] = hit
        else:
            by_key[(hit.path, hit.record_size, hit.fields, hit.offset)] = hit
    return list(by_key.values())


def format_record(record: tuple[int, ...]) -> str:
    return "(" + ", ".join(f"{value:03d}" for value in record) + ")"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find candidate fixed-width tables containing Yu-Gi-Oh card-like numeric IDs."
    )
    parser.add_argument("paths", nargs="+", type=pathlib.Path)
    parser.add_argument("--max-card-id", type=int, default=722)
    parser.add_argument("--min-records", type=int, default=16)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--record-sizes", default="6,8,10,12,16")
    parser.add_argument("--fields", default="3,4")
    args = parser.parse_args()

    record_sizes = [int(value) for value in args.record_sizes.split(",") if value]
    fields_options = [int(value) for value in args.fields.split(",") if value]

    files: list[pathlib.Path] = []
    for path in args.paths:
        if path.is_dir():
            files.extend(p for p in path.rglob("*") if p.is_file())
        else:
            files.append(path)

    hits: list[Hit] = []
    for path in files:
        hits.extend(find_runs(path, args.min_records, args.max_card_id, record_sizes, fields_options))

    hits = collapse_overlapping(hits)
    hits.sort(key=lambda h: (h.score, h.count), reverse=True)

    for hit in hits[: args.limit]:
        samples = " ".join(format_record(record) for record in hit.sample)
        print(
            f"{hit.path}\toffset=0x{hit.offset:08X}\trec={hit.record_size}\t"
            f"fields={hit.fields}\tcount={hit.count}\tscore={hit.score:.3f}\t{samples}"
        )


if __name__ == "__main__":
    main()
