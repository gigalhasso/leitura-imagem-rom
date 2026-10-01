from __future__ import annotations

import argparse
import csv
import json
import pathlib
import struct

from extract_drops import (
    DEFAULT_DUELIST_BLOCK_OFFSET,
    DEFAULT_DUELIST_BLOCK_SIZE,
    DEFAULT_DUELIST_COUNT,
    DEFAULT_DUELIST_NAMES_OFFSET,
    DROP_DENOMINATOR,
    read_duelist_names,
)
from extract_fusions import (
    DEFAULT_CARD_COUNT,
    DEFAULT_LEVEL_ATTRIBUTE_OFFSET,
    DEFAULT_NAME_POINTER_BIAS,
    DEFAULT_NAME_POINTERS_OFFSET,
    DEFAULT_STATS_OFFSET,
    load_character_table,
    read_cards,
)


def write_csv(path: pathlib.Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract the weighted card pool used to build every opponent deck."
    )
    parser.add_argument("wa_mrg", type=pathlib.Path)
    parser.add_argument("slus", type=pathlib.Path)
    parser.add_argument(
        "--character-table",
        type=pathlib.Path,
        default=pathlib.Path("references/chartable.tbl"),
    )
    parser.add_argument(
        "--output-dir",
        type=pathlib.Path,
        default=pathlib.Path("exports/opponent_decks"),
    )
    parser.add_argument("--card-count", type=int, default=DEFAULT_CARD_COUNT)
    parser.add_argument("--duelist-count", type=int, default=DEFAULT_DUELIST_COUNT)
    args = parser.parse_args()

    wa_mrg = args.wa_mrg.read_bytes()
    slus = args.slus.read_bytes()
    character_table = load_character_table(args.character_table)
    cards = read_cards(
        slus,
        character_table,
        args.card_count,
        DEFAULT_STATS_OFFSET,
        DEFAULT_LEVEL_ATTRIBUTE_OFFSET,
        DEFAULT_NAME_POINTERS_OFFSET,
        DEFAULT_NAME_POINTER_BIAS,
    )
    duelist_names = read_duelist_names(
        slus,
        character_table,
        args.duelist_count,
        DEFAULT_DUELIST_NAMES_OFFSET,
        DEFAULT_NAME_POINTER_BIAS,
    )

    fields = [
        "duelist_id",
        "duelist_name",
        "card_id",
        "card_name",
        "weight",
        "denominator",
        "rate_fraction",
        "probability_percent",
        "average_one_in",
        "wa_mrg_offset",
    ]
    all_rows: list[dict[str, object]] = []
    possible_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    nested: list[dict[str, object]] = []

    for duelist_index, duelist_name in enumerate(duelist_names):
        table_offset = DEFAULT_DUELIST_BLOCK_OFFSET + duelist_index * DEFAULT_DUELIST_BLOCK_SIZE
        table_end = table_offset + args.card_count * 2
        if table_end > len(wa_mrg):
            raise ValueError(
                f"Deck table exceeds WA_MRG: duelist={duelist_name}, "
                f"end=0x{table_end:X}, size=0x{len(wa_mrg):X}"
            )
        weights = struct.unpack_from(f"<{args.card_count}H", wa_mrg, table_offset)
        total_weight = sum(weights)
        if total_weight != DROP_DENOMINATOR:
            raise ValueError(
                f"Invalid deck pool total for {duelist_name}: "
                f"expected {DROP_DENOMINATOR}, found {total_weight}"
            )

        duelist_cards: list[dict[str, object]] = []
        for card, weight in zip(cards, weights):
            probability = weight / DROP_DENOMINATOR * 100
            row = {
                "duelist_id": duelist_index + 1,
                "duelist_name": duelist_name,
                "card_id": card.card_id,
                "card_name": card.name,
                "weight": weight,
                "denominator": DROP_DENOMINATOR,
                "rate_fraction": f"{weight}/{DROP_DENOMINATOR}",
                "probability_percent": f"{probability:.6f}",
                "average_one_in": f"{DROP_DENOMINATOR / weight:.3f}" if weight else "",
                "wa_mrg_offset": f"0x{table_offset + (card.card_id - 1) * 2:08X}",
            }
            all_rows.append(row)
            if weight:
                possible_rows.append(row)
                duelist_cards.append(
                    {
                        "card_id": card.card_id,
                        "card_name": card.name,
                        "weight": weight,
                        "denominator": DROP_DENOMINATOR,
                        "probability_percent": round(probability, 6),
                    }
                )

        summary_rows.append(
            {
                "duelist_id": duelist_index + 1,
                "duelist_name": duelist_name,
                "possible_cards": len(duelist_cards),
                "total_weight": total_weight,
                "highest_weight": max(weights),
                "table_offset": f"0x{table_offset:08X}",
            }
        )
        nested.append(
            {
                "duelist_id": duelist_index + 1,
                "duelist_name": duelist_name,
                "total_weight": total_weight,
                "cards": duelist_cards,
            }
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    possible_path = args.output_dir / "opponent_deck_rates.csv"
    all_path = args.output_dir / "opponent_deck_rates_all_cards.csv"
    summary_csv_path = args.output_dir / "opponent_decks_summary.csv"
    json_path = args.output_dir / "opponent_deck_rates.json"
    guide_path = args.output_dir / "guia_decks_oponentes_pt_br.md"
    summary_path = args.output_dir / "summary.json"

    write_csv(possible_path, possible_rows, fields)
    write_csv(all_path, all_rows, fields)
    write_csv(
        summary_csv_path,
        summary_rows,
        [
            "duelist_id",
            "duelist_name",
            "possible_cards",
            "total_weight",
            "highest_weight",
            "table_offset",
        ],
    )
    json_path.write_text(json.dumps(nested, indent=2, ensure_ascii=False), encoding="utf-8")

    guide_lines = [
        "# Cartas usadas pelos oponentes",
        "",
        "Cada oponente possui um unico pool ponderado para montar seu deck.",
        "Cada peso e armazenado como `x/2048`, e cada pool soma exatamente 2048.",
        "",
        "O percentual representa uma tentativa de selecao durante a montagem do deck.",
        "Depois de formado, o baralho de 40 cartas e embaralhado; portanto, o peso bruto",
        "nao deve ser interpretado como a chance exata de comprar a carta em um turno especifico.",
        "",
        "## Resumo",
        "",
        "| ID | Oponente | Cartas possiveis | Maior peso |",
        "|---:|---|---:|---:|",
    ]
    for row in summary_rows:
        guide_lines.append(
            f"| {row['duelist_id']} | {row['duelist_name']} | "
            f"{row['possible_cards']} | {row['highest_weight']}/2048 |"
        )
    guide_path.write_text("\n".join(guide_lines) + "\n", encoding="utf-8")

    summary = {
        "duelist_count": len(duelist_names),
        "pool_count": len(duelist_names),
        "card_count": len(cards),
        "possible_card_rows": len(possible_rows),
        "all_rows_including_zero": len(all_rows),
        "validated_pool_total": DROP_DENOMINATOR,
        "files": {
            "possible_cards_csv": str(possible_path),
            "all_cards_csv": str(all_path),
            "opponents_summary_csv": str(summary_csv_path),
            "decks_json": str(json_path),
            "guide_pt_br": str(guide_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
