from __future__ import annotations

import argparse
import csv
import json
import pathlib
import struct
from dataclasses import asdict, dataclass


DEFAULT_FUSION_OFFSET = 0xB87800
DEFAULT_FUSION_REGION_SIZE = 0x10000
DEFAULT_CARD_COUNT = 722
DEFAULT_STATS_OFFSET = 0x1C4A44
DEFAULT_LEVEL_ATTRIBUTE_OFFSET = 0x1C5B33
DEFAULT_NAME_POINTERS_OFFSET = 0x1C6002
DEFAULT_NAME_POINTER_BIAS = 0x1C0800


@dataclass(frozen=True)
class Card:
    card_id: int
    name: str
    attack: int
    defense: int
    guardian_star_1: int
    guardian_star_2: int
    card_type: int
    level: int
    attribute: int


@dataclass(frozen=True)
class Fusion:
    card_a_id: int
    card_b_id: int
    result_id: int


@dataclass(frozen=True)
class DeclaredFusion:
    sequence: int
    list_card_id: int
    list_entry_index: int
    card_b_id: int
    result_id: int
    byte_offset_in_fusion_region: int


def read_u16le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def load_character_table(path: pathlib.Path) -> dict[int, str]:
    table: dict[int, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line or raw_line.startswith("#"):
            continue
        if "=" not in raw_line:
            raise ValueError(f"Invalid character table line {line_number}: {raw_line!r}")
        raw_byte, character = raw_line.split("=", 1)
        table[int(raw_byte, 16)] = "\n" if character == "[ENTER]" else character
    return table


def decode_text(data: bytes, offset: int, character_table: dict[int, str]) -> str:
    characters: list[str] = []
    while offset < len(data):
        value = data[offset]
        offset += 1
        if value == 0xFF:
            break
        if value == 0xF8:
            # This mod prefixes some names with F8 0A xx formatting metadata.
            offset += 2
            continue
        characters.append(character_table.get(value, ""))
    return "".join(characters).replace("\n", " ").strip()


def read_cards(
    slus: bytes,
    character_table: dict[int, str],
    card_count: int,
    stats_offset: int,
    level_attribute_offset: int,
    name_pointers_offset: int,
    name_pointer_bias: int,
) -> list[Card]:
    cards: list[Card] = []
    required_end = max(
        stats_offset + card_count * 4,
        level_attribute_offset + card_count,
        name_pointers_offset + card_count * 2,
    )
    if required_end > len(slus):
        raise ValueError(
            f"Card tables exceed SLUS size: required=0x{required_end:X}, size=0x{len(slus):X}"
        )

    for index in range(card_count):
        packed = struct.unpack_from("<I", slus, stats_offset + index * 4)[0]
        level_attribute = slus[level_attribute_offset + index]
        name_pointer = read_u16le(slus, name_pointers_offset + index * 2)
        name_offset = name_pointer_bias + name_pointer
        if name_offset >= len(slus):
            raise ValueError(
                f"Card {index + 1} name offset is outside SLUS: 0x{name_offset:X}"
            )
        cards.append(
            Card(
                card_id=index + 1,
                name=decode_text(slus, name_offset, character_table),
                attack=(packed & 0x1FF) * 10,
                defense=((packed >> 9) & 0x1FF) * 10,
                guardian_star_1=(packed >> 18) & 0xF,
                guardian_star_2=(packed >> 22) & 0xF,
                card_type=(packed >> 26) & 0x1F,
                level=level_attribute & 0xF,
                attribute=(level_attribute >> 4) & 0xF,
            )
        )
    return cards


def read_fusion_count(region: bytes, offset: int) -> tuple[int, int]:
    count = region[offset]
    offset += 1
    if count == 0:
        count = 511 - region[offset]
        offset += 1
    return count, offset


def unpack_fusion_pair(block: bytes) -> tuple[tuple[int, int], tuple[int, int]]:
    high_bits, material_1, result_1, material_2, result_2 = block
    first = (((high_bits & 0x03) << 8) | material_1, ((high_bits & 0x0C) << 6) | result_1)
    second = (
        ((high_bits & 0x30) << 4) | material_2,
        ((high_bits & 0xC0) << 2) | result_2,
    )
    return first, second


def read_declared_fusions(region: bytes, card_count: int) -> list[DeclaredFusion]:
    declared: list[DeclaredFusion] = []
    sequence = 0
    for card_id in range(1, card_count + 1):
        pointer = read_u16le(region, card_id * 2)
        if pointer == 0:
            continue
        count, position = read_fusion_count(region, pointer)
        entry_index = 0
        while entry_index < count:
            if position + 5 > len(region):
                raise ValueError(
                    f"Fusion block for card {card_id} exceeds region at 0x{position:X}"
                )
            pairs = unpack_fusion_pair(region[position : position + 5])
            for card_b_id, result_id in pairs:
                if entry_index >= count:
                    break
                if not (1 <= card_b_id <= card_count and 1 <= result_id <= card_count):
                    raise ValueError(
                        f"Invalid fusion ID at 0x{position:X}: {card_id} + {card_b_id} = {result_id}"
                    )
                declared.append(
                    DeclaredFusion(
                        sequence=sequence,
                        list_card_id=card_id,
                        list_entry_index=entry_index,
                        card_b_id=card_b_id,
                        result_id=result_id,
                        byte_offset_in_fusion_region=position,
                    )
                )
                sequence += 1
                entry_index += 1
            position += 5
    return declared


def lookup_fusion(region: bytes, card_a_id: int, card_b_id: int) -> int:
    if card_b_id < card_a_id:
        card_a_id, card_b_id = card_b_id, card_a_id
    pointer = read_u16le(region, card_a_id * 2)
    if pointer == 0:
        return 0

    count, position = read_fusion_count(region, pointer)
    remaining = count
    while remaining > 0:
        first, second = unpack_fusion_pair(region[position : position + 5])
        if first[0] == card_b_id:
            return first[1]
        # The original routine always checks the second slot, even when count is odd.
        if second[0] == card_b_id:
            return second[1]
        remaining -= 2
        position += 5
    return 0


def read_effective_fusions(region: bytes, card_count: int) -> list[Fusion]:
    effective: list[Fusion] = []
    for card_a_id in range(1, card_count + 1):
        for card_b_id in range(card_a_id, card_count + 1):
            result_id = lookup_fusion(region, card_a_id, card_b_id)
            if result_id:
                if not 1 <= result_id <= card_count:
                    raise ValueError(
                        f"Effective fusion has invalid result: {card_a_id} + {card_b_id} = {result_id}"
                    )
                effective.append(Fusion(card_a_id, card_b_id, result_id))
    return effective


def write_cards(path: pathlib.Path, cards: list[Card], delimiter: str) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(asdict(cards[0])), delimiter=delimiter)
        writer.writeheader()
        writer.writerows(asdict(card) for card in cards)


def write_effective_fusions(
    path: pathlib.Path,
    effective: list[Fusion],
    declared: list[DeclaredFusion],
    cards_by_id: dict[int, Card],
    delimiter: str,
) -> None:
    declared_triples = {
        (item.list_card_id, item.card_b_id, item.result_id) for item in declared
    }
    fields = [
        "card_a_id",
        "card_a_name",
        "card_b_id",
        "card_b_name",
        "result_id",
        "result_name",
        "origin",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=fields, delimiter=delimiter)
        writer.writeheader()
        for fusion in effective:
            triple = (fusion.card_a_id, fusion.card_b_id, fusion.result_id)
            writer.writerow(
                {
                    "card_a_id": fusion.card_a_id,
                    "card_a_name": cards_by_id[fusion.card_a_id].name,
                    "card_b_id": fusion.card_b_id,
                    "card_b_name": cards_by_id[fusion.card_b_id].name,
                    "result_id": fusion.result_id,
                    "result_name": cards_by_id[fusion.result_id].name,
                    "origin": "declared" if triple in declared_triples else "glitch_odd_list",
                }
            )


def write_declared_fusions(
    path: pathlib.Path,
    declared: list[DeclaredFusion],
    region: bytes,
    cards_by_id: dict[int, Card],
    delimiter: str,
    fusion_offset: int,
) -> None:
    fields = [
        "sequence",
        "list_card_id",
        "list_card_name",
        "list_entry_index",
        "card_b_id",
        "card_b_name",
        "result_id",
        "result_name",
        "byte_offset_in_fusion_region",
        "absolute_wa_mrg_offset",
        "status",
        "effective_result_id",
        "effective_result_name",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=fields, delimiter=delimiter)
        writer.writeheader()
        for item in declared:
            effective_result = lookup_fusion(region, item.list_card_id, item.card_b_id)
            if item.card_b_id < item.list_card_id:
                status = "unreachable_reversed_pair"
            elif effective_result == item.result_id:
                status = "effective"
            elif effective_result:
                status = "shadowed_by_earlier_result"
            else:
                status = "not_returned"
            writer.writerow(
                {
                    "sequence": item.sequence,
                    "list_card_id": item.list_card_id,
                    "list_card_name": cards_by_id[item.list_card_id].name,
                    "list_entry_index": item.list_entry_index,
                    "card_b_id": item.card_b_id,
                    "card_b_name": cards_by_id[item.card_b_id].name,
                    "result_id": item.result_id,
                    "result_name": cards_by_id[item.result_id].name,
                    "byte_offset_in_fusion_region": f"0x{item.byte_offset_in_fusion_region:04X}",
                    "absolute_wa_mrg_offset": (
                        f"0x{fusion_offset + item.byte_offset_in_fusion_region:08X}"
                    ),
                    "status": status,
                    "effective_result_id": effective_result or "",
                    "effective_result_name": (
                        cards_by_id[effective_result].name if effective_result else ""
                    ),
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract the compressed Forbidden Memories card and fusion tables."
    )
    parser.add_argument("wa_mrg", type=pathlib.Path)
    parser.add_argument("slus", type=pathlib.Path)
    parser.add_argument("--character-table", type=pathlib.Path, default=pathlib.Path("references/chartable.tbl"))
    parser.add_argument("--output-dir", type=pathlib.Path, default=pathlib.Path("exports/fusions"))
    parser.add_argument("--delimiter", default=";", help="CSV delimiter; defaults to ';' for pt-BR Excel.")
    parser.add_argument("--fusion-offset", type=lambda value: int(value, 0), default=DEFAULT_FUSION_OFFSET)
    parser.add_argument("--fusion-region-size", type=lambda value: int(value, 0), default=DEFAULT_FUSION_REGION_SIZE)
    parser.add_argument("--card-count", type=int, default=DEFAULT_CARD_COUNT)
    parser.add_argument("--stats-offset", type=lambda value: int(value, 0), default=DEFAULT_STATS_OFFSET)
    parser.add_argument(
        "--level-attribute-offset",
        type=lambda value: int(value, 0),
        default=DEFAULT_LEVEL_ATTRIBUTE_OFFSET,
    )
    parser.add_argument(
        "--name-pointers-offset",
        type=lambda value: int(value, 0),
        default=DEFAULT_NAME_POINTERS_OFFSET,
    )
    parser.add_argument(
        "--name-pointer-bias",
        type=lambda value: int(value, 0),
        default=DEFAULT_NAME_POINTER_BIAS,
    )
    args = parser.parse_args()

    wa_mrg = args.wa_mrg.read_bytes()
    fusion_end = args.fusion_offset + args.fusion_region_size
    if fusion_end > len(wa_mrg):
        raise ValueError(
            f"Fusion region exceeds WA_MRG: end=0x{fusion_end:X}, size=0x{len(wa_mrg):X}"
        )
    region = wa_mrg[args.fusion_offset:fusion_end]
    character_table = load_character_table(args.character_table)
    cards = read_cards(
        args.slus.read_bytes(),
        character_table,
        args.card_count,
        args.stats_offset,
        args.level_attribute_offset,
        args.name_pointers_offset,
        args.name_pointer_bias,
    )
    cards_by_id = {card.card_id: card for card in cards}
    declared = read_declared_fusions(region, args.card_count)
    effective = read_effective_fusions(region, args.card_count)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    cards_path = args.output_dir / "cards.csv"
    effective_path = args.output_dir / "fusions_effective.csv"
    declared_path = args.output_dir / "fusions_declared_raw.csv"
    summary_path = args.output_dir / "summary.json"
    write_cards(cards_path, cards, args.delimiter)
    write_effective_fusions(effective_path, effective, declared, cards_by_id, args.delimiter)
    write_declared_fusions(
        declared_path,
        declared,
        region,
        cards_by_id,
        args.delimiter,
        args.fusion_offset,
    )

    declared_triples = {
        (item.list_card_id, item.card_b_id, item.result_id) for item in declared
    }
    glitch_count = sum(
        (fusion.card_a_id, fusion.card_b_id, fusion.result_id) not in declared_triples
        for fusion in effective
    )
    summary = {
        "card_count": len(cards),
        "fusion_region_offset": f"0x{args.fusion_offset:08X}",
        "declared_records": len(declared),
        "unique_declared_triples": len(declared_triples),
        "effective_fusions": len(effective),
        "glitch_fusions_from_odd_lists": glitch_count,
        "files": {
            "cards": str(cards_path),
            "effective_fusions": str(effective_path),
            "declared_fusions": str(declared_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
