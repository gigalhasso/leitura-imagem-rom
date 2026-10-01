from __future__ import annotations

import csv
import json
from pathlib import Path

from extract_fusions import decode_text, load_character_table, read_u16le


ROOT = Path(__file__).resolve().parent.parent
EXPORTS = ROOT / "exports"
OUTPUT = ROOT / "catalogo" / "data.js"
CHARACTER_TABLE = ROOT / "references" / "chartable.tbl"
DESCRIPTION_POINTERS_OFFSET = 0x001B0A00
DESCRIPTION_POINTER_BIAS = 0x001B0800
DESCRIPTION_POINTER_COUNT = 723  # index zero is reserved; cards use indexes 1..722
DATASET_EXECUTABLES = {
    "remastered": ROOT / "extracted" / "SLUS_014.11",
    "naruto": ROOT / "extracted_naruto" / "SLUS_025.11",
    "naruto_shippuden_final": ROOT / "extracted_naruto_shippuden_final" / "SLUS_096.11",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file, delimiter=";"))


def compact(rows: list[dict[str, str]], keys: list[str]) -> list[list[str]]:
    return [[row[key] for key in keys] for row in rows]


def load_mod_descriptions(slus_path: Path) -> dict[str, str]:
    """Read the 722 card descriptions directly from a mod executable."""
    slus = slus_path.read_bytes()
    table_end = DESCRIPTION_POINTERS_OFFSET + DESCRIPTION_POINTER_COUNT * 2
    if table_end > len(slus):
        raise ValueError(f"Description pointer table exceeds {slus_path}")
    character_table = load_character_table(CHARACTER_TABLE)
    descriptions: dict[str, str] = {}
    for card_id in range(1, DESCRIPTION_POINTER_COUNT):
        pointer = read_u16le(slus, DESCRIPTION_POINTERS_OFFSET + card_id * 2)
        text_offset = DESCRIPTION_POINTER_BIAS + pointer
        if text_offset >= len(slus):
            raise ValueError(f"Card {card_id} description offset is outside {slus_path}")
        descriptions[str(card_id)] = decode_text(slus, text_offset, character_table)
    return descriptions


def validate_references(
    cards: list[dict[str, str]],
    tables: list[tuple[str, list[dict[str, str]], list[str]]],
) -> None:
    card_ids = [row["card_id"] for row in cards]
    if len(card_ids) != len(set(card_ids)):
        raise ValueError("Duplicate card IDs in cards.csv")

    valid_ids = set(card_ids)
    for table_name, rows, fields in tables:
        for row_number, row in enumerate(rows, start=2):
            for field in fields:
                if row[field] not in valid_ids:
                    raise ValueError(
                        f"{table_name}:{row_number} references unknown {field}={row[field]}"
                    )


def build_dataset(
    base: Path,
    meta: dict[str, str],
    descriptions: dict[str, str],
) -> dict[str, object]:
    cards = read_csv(base / "fusions" / "cards.csv")
    for card in cards:
        card["description"] = descriptions.get(card["card_id"], "")
    fusions = read_csv(base / "fusions" / "fusions_effective.csv")
    drops = read_csv(base / "drops" / "drop_rates.csv")
    decks = read_csv(base / "opponent_decks" / "opponent_deck_rates.csv")
    pools = read_csv(base / "drops" / "drop_pools_summary.csv")
    opponents = read_csv(base / "opponent_decks" / "opponent_decks_summary.csv")
    equipment = read_csv(base / "equipment" / "equipment_compatibility.csv")

    validate_references(cards, [
        ("fusions", fusions, ["card_a_id", "card_b_id", "result_id"]),
        ("drops", drops, ["card_id"]),
        ("decks", decks, ["card_id"]),
        ("equipment", equipment, ["card_id", "equip_id"]),
    ])

    return {
        "meta": meta,
        "cards": compact(cards, ["card_id", "name", "attack", "defense", "guardian_star_1", "guardian_star_2", "card_type", "level", "attribute", "description"]),
        "fusions": compact(fusions, ["card_a_id", "card_b_id", "result_id", "origin"]),
        "drops": compact(drops, ["duelist_id", "pool_code", "card_id", "weight", "denominator"]),
        "decks": compact(decks, ["duelist_id", "card_id", "weight", "denominator"]),
        "pools": compact(pools, ["duelist_id", "duelist_name", "pool_code", "pool_name", "ranks", "possible_cards", "total_weight"]),
        "opponents": compact(opponents, ["duelist_id", "duelist_name", "possible_cards", "total_weight", "highest_weight"]),
        "equipment": compact(equipment, ["card_id", "equip_id"]),
    }


def main() -> None:
    descriptions_by_dataset = {
        dataset_key: load_mod_descriptions(slus_path)
        for dataset_key, slus_path in DATASET_EXECUTABLES.items()
    }
    payload = {
        "defaultDataset": "remastered",
        "datasets": {
            "remastered": build_dataset(EXPORTS, {
                "label": "Remastered Perfected",
                "shortLabel": "Remastered",
                "title": "Base de cartas do Remastered Perfected",
                "description": "Cartas, fusões, drops, decks e equipamentos extraídos da versão DROP x15.",
                "footer": "Yu-Gi-Oh! Forbidden Memories Remastered Perfected · dados extraídos localmente",
            }, descriptions_by_dataset["remastered"]),
            "naruto": build_dataset(EXPORTS / "naruto", {
                "label": "Naruto Drop x15",
                "shortLabel": "Naruto",
                "title": "Base de cartas do mod Naruto",
                "description": "Cartas, fusões, drops, decks e equipamentos extraídos da versão Naruto DROP x15.",
                "footer": "Yu-Gi-Oh! Forbidden Memories Naruto · dados extraídos localmente",
            }, descriptions_by_dataset["naruto"]),
            "naruto_shippuden_final": build_dataset(EXPORTS / "naruto_shippuden_final", {
                "label": "Naruto Shippuden Final",
                "shortLabel": "Naruto Shippuden Final",
                "title": "Base de cartas do Naruto Shippuden Final",
                "description": "Cartas, fusões, drops, decks e equipamentos extraídos do mod Naruto Shippuden FM Final.",
                "footer": "Yu-Gi-Oh! Forbidden Memories Naruto Shippuden Final · dados extraídos localmente",
            }, descriptions_by_dataset["naruto_shippuden_final"]),
        },
    }
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text("window.CATALOG_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"Generated {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
