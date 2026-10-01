from __future__ import annotations

import argparse
import csv
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WA_MRG = ROOT / "extracted" / "DATA" / "WA_MRG.MRG"
DEFAULT_CARDS_CSV = ROOT / "exports" / "fusions" / "cards.csv"
DEFAULT_OUTPUT_DIR = ROOT / "exports" / "equipment"
TABLE_OFFSET = 0x00B85000


def read_cards(path: Path) -> dict[int, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return {
            int(row["card_id"]): row
            for row in csv.DictReader(file, delimiter=";")
        }


def parse_table(data: bytes, table_offset: int) -> tuple[list[dict[str, object]], int]:
    records: list[dict[str, object]] = []
    offset = table_offset

    while True:
        equip_id, count = struct.unpack_from("<HH", data, offset)
        if equip_id == 0:
            return records, offset

        values_offset = offset + 4
        accepted_ids = list(
            struct.unpack_from(f"<{count}H", data, values_offset)
        )
        records.append(
            {
                "equip_id": equip_id,
                "accepted_ids": accepted_ids,
                "record_offset": offset,
            }
        )
        offset = values_offset + count * 2


def validate(records: list[dict[str, object]], cards: dict[int, dict[str, str]]) -> None:
    equip_ids = {card_id for card_id, card in cards.items() if int(card["card_type"]) == 23}
    parsed_equip_ids = {int(record["equip_id"]) for record in records}

    unknown_equip_ids = parsed_equip_ids - equip_ids
    if unknown_equip_ids:
        raise ValueError(
            f"Equipment table contains cards not marked as Equip: {sorted(unknown_equip_ids)}"
        )

    invalid_targets = {
        int(card_id)
        for record in records
        for card_id in record["accepted_ids"]
        if int(card_id) not in cards
    }
    if invalid_targets:
        raise ValueError(f"Unknown card IDs in equipment table: {sorted(invalid_targets)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract equipment compatibility from WA_MRG.")
    parser.add_argument("wa_mrg", type=Path, nargs="?", default=DEFAULT_WA_MRG)
    parser.add_argument("--cards-csv", type=Path, default=DEFAULT_CARDS_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--table-offset", type=lambda value: int(value, 0), default=TABLE_OFFSET)
    args = parser.parse_args()

    cards = read_cards(args.cards_csv)
    records, sentinel_offset = parse_table(args.wa_mrg.read_bytes(), args.table_offset)
    validate(records, cards)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for record in records:
        equip_id = int(record["equip_id"])
        for card_id in record["accepted_ids"]:
            card_id = int(card_id)
            rows.append(
                {
                    "card_id": card_id,
                    "card_name": cards[card_id]["name"],
                    "equip_id": equip_id,
                    "equip_name": cards[equip_id]["name"],
                    "record_offset": f"0x{int(record['record_offset']):08X}",
                }
            )

    csv_path = args.output_dir / "equipment_compatibility.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys(), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    accepted_by_card = {
        card_id: [
            int(record["equip_id"])
            for record in records
            if card_id in record["accepted_ids"]
        ]
        for card_id in sorted(cards)
    }
    referenced_targets = {
        int(card_id)
        for record in records
        for card_id in record["accepted_ids"]
    }
    non_monster_targets = sorted(
        card_id for card_id in referenced_targets if int(cards[card_id]["card_type"]) >= 20
    )
    metadata_equip_ids = {
        card_id for card_id, card in cards.items() if int(card["card_type"]) == 23
    }
    parsed_equip_ids = {int(record["equip_id"]) for record in records}
    summary = {
        "table_offset": f"0x{args.table_offset:08X}",
        "sentinel_offset": f"0x{sentinel_offset:08X}",
        "equip_records": len(records),
        "equip_cards_without_record": sorted(metadata_equip_ids - parsed_equip_ids),
        "compatibility_relations": len(rows),
        "monster_cards": sum(int(card["card_type"]) < 20 for card in cards.values()),
        "equipment_target_cards": len(referenced_targets),
        "non_monster_target_cards": non_monster_targets,
        "baby_dragon_id_1": accepted_by_card[1],
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
