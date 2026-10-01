from __future__ import annotations

import argparse
import csv
import json
import pathlib
import struct

from extract_fusions import (
    DEFAULT_CARD_COUNT,
    DEFAULT_LEVEL_ATTRIBUTE_OFFSET,
    DEFAULT_NAME_POINTER_BIAS,
    DEFAULT_NAME_POINTERS_OFFSET,
    DEFAULT_STATS_OFFSET,
    decode_text,
    load_character_table,
    read_cards,
    read_u16le,
)


DEFAULT_DUELIST_COUNT = 39
DEFAULT_DUELIST_NAMES_OFFSET = 0x1C6652
DEFAULT_DUELIST_BLOCK_OFFSET = 0xE9B000
DEFAULT_DUELIST_BLOCK_SIZE = 0x1800
DROP_DENOMINATOR = 2048

POOL_DEFINITIONS = (
    ("SA_POW", "S/A POW", "S-POW ou A-POW", 0x05B4),
    ("BCD_POW_TEC", "B/C/D POW/TEC", "B/C/D-POW ou B/C/D-TEC", 0x0B68),
    ("SA_TEC", "S/A TEC", "S-TEC ou A-TEC", 0x111C),
)


def read_duelist_names(
    slus: bytes,
    character_table: dict[int, str],
    count: int,
    pointer_table_offset: int,
    pointer_bias: int,
) -> list[str]:
    names: list[str] = []
    for index in range(count):
        pointer = read_u16le(slus, pointer_table_offset + index * 2)
        names.append(decode_text(slus, pointer_bias + pointer, character_table))
    return names


def write_csv(path: pathlib.Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract all Forbidden Memories opponent card-drop probabilities."
    )
    parser.add_argument("wa_mrg", type=pathlib.Path)
    parser.add_argument("slus", type=pathlib.Path)
    parser.add_argument(
        "--character-table",
        type=pathlib.Path,
        default=pathlib.Path("references/chartable.tbl"),
    )
    parser.add_argument(
        "--output-dir", type=pathlib.Path, default=pathlib.Path("exports/drops")
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

    all_rows: list[dict[str, object]] = []
    possible_rows: list[dict[str, object]] = []
    pool_rows: list[dict[str, object]] = []
    nested: list[dict[str, object]] = []

    row_fields = [
        "duelist_id",
        "duelist_name",
        "pool_code",
        "pool_name",
        "ranks",
        "card_id",
        "card_name",
        "weight",
        "denominator",
        "rate_fraction",
        "probability_percent",
        "average_one_in",
        "wa_mrg_offset",
    ]

    for duelist_index, duelist_name in enumerate(duelist_names):
        duelist_pools: list[dict[str, object]] = []
        block_offset = DEFAULT_DUELIST_BLOCK_OFFSET + duelist_index * DEFAULT_DUELIST_BLOCK_SIZE
        for pool_code, pool_name, ranks, relative_offset in POOL_DEFINITIONS:
            table_offset = block_offset + relative_offset
            table_end = table_offset + args.card_count * 2
            if table_end > len(wa_mrg):
                raise ValueError(
                    f"Drop table exceeds WA_MRG: duelist={duelist_name}, "
                    f"pool={pool_code}, end=0x{table_end:X}, size=0x{len(wa_mrg):X}"
                )
            weights = struct.unpack_from(f"<{args.card_count}H", wa_mrg, table_offset)
            total_weight = sum(weights)
            if total_weight != DROP_DENOMINATOR:
                raise ValueError(
                    f"Invalid pool total for {duelist_name} {pool_code}: "
                    f"expected {DROP_DENOMINATOR}, found {total_weight}"
                )

            pool_drops: list[dict[str, object]] = []
            for card, weight in zip(cards, weights):
                probability = weight / DROP_DENOMINATOR * 100
                row = {
                    "duelist_id": duelist_index + 1,
                    "duelist_name": duelist_name,
                    "pool_code": pool_code,
                    "pool_name": pool_name,
                    "ranks": ranks,
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
                    pool_drops.append(
                        {
                            "card_id": card.card_id,
                            "card_name": card.name,
                            "weight": weight,
                            "denominator": DROP_DENOMINATOR,
                            "probability_percent": round(probability, 6),
                        }
                    )

            pool_rows.append(
                {
                    "duelist_id": duelist_index + 1,
                    "duelist_name": duelist_name,
                    "pool_code": pool_code,
                    "pool_name": pool_name,
                    "ranks": ranks,
                    "possible_cards": len(pool_drops),
                    "total_weight": total_weight,
                    "table_offset": f"0x{table_offset:08X}",
                }
            )
            duelist_pools.append(
                {
                    "pool_code": pool_code,
                    "pool_name": pool_name,
                    "ranks": ranks,
                    "total_weight": total_weight,
                    "drops": pool_drops,
                }
            )
        nested.append(
            {
                "duelist_id": duelist_index + 1,
                "duelist_name": duelist_name,
                "pools": duelist_pools,
            }
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    possible_path = args.output_dir / "drop_rates.csv"
    all_path = args.output_dir / "drop_rates_all_cards.csv"
    pools_path = args.output_dir / "drop_pools_summary.csv"
    json_path = args.output_dir / "drop_rates.json"
    guide_path = args.output_dir / "guia_drops_pt_br.md"
    summary_path = args.output_dir / "summary.json"

    write_csv(possible_path, possible_rows, row_fields)
    write_csv(all_path, all_rows, row_fields)
    write_csv(
        pools_path,
        pool_rows,
        [
            "duelist_id",
            "duelist_name",
            "pool_code",
            "pool_name",
            "ranks",
            "possible_cards",
            "total_weight",
            "table_offset",
        ],
    )
    json_path.write_text(json.dumps(nested, indent=2, ensure_ascii=False), encoding="utf-8")

    guide_lines = [
        "# Guia de drops do mod",
        "",
        "Cada adversario possui tres pools. O rank final escolhe qual pool sera usado:",
        "",
        "- `S/A POW`: vitorias com rank S-POW ou A-POW.",
        "- `B/C/D POW/TEC`: ranks B, C ou D, tanto POW quanto TEC.",
        "- `S/A TEC`: vitorias com rank S-TEC ou A-TEC.",
        "",
        "O peso de cada carta e `x/2048`. Os pesos de todo pool somam exatamente 2048.",
        "O CSV principal registra a chance por sorteio de carta; o modificador Drop x15",
        "nao altera o denominador armazenado nestas tabelas.",
        "",
        "## Quantidade de cartas possiveis por oponente",
        "",
        "| ID | Oponente | S/A POW | B/C/D POW/TEC | S/A TEC |",
        "|---:|---|---:|---:|---:|",
    ]
    counts_by_duelist: dict[int, dict[str, int]] = {}
    for row in pool_rows:
        counts_by_duelist.setdefault(int(row["duelist_id"]), {})[str(row["pool_code"])] = int(
            row["possible_cards"]
        )
    for duelist_id, duelist_name in enumerate(duelist_names, 1):
        counts = counts_by_duelist[duelist_id]
        guide_lines.append(
            f"| {duelist_id} | {duelist_name} | {counts['SA_POW']} | "
            f"{counts['BCD_POW_TEC']} | {counts['SA_TEC']} |"
        )
    guide_path.write_text("\n".join(guide_lines) + "\n", encoding="utf-8")

    summary = {
        "duelist_count": len(duelist_names),
        "pool_count": len(pool_rows),
        "pool_types": len(POOL_DEFINITIONS),
        "card_count": len(cards),
        "possible_drop_rows": len(possible_rows),
        "all_drop_rows_including_zero": len(all_rows),
        "validated_pool_total": DROP_DENOMINATOR,
        "files": {
            "possible_drops_csv": str(possible_path),
            "all_cards_csv": str(all_path),
            "pool_summary_csv": str(pools_path),
            "drops_json": str(json_path),
            "guide_pt_br": str(guide_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
