from __future__ import annotations

import argparse
import csv
import json
import pathlib
from collections import Counter, defaultdict, deque
from dataclasses import dataclass


CARD_TYPES = {
    0x00: "Dragon",
    0x01: "Spellcaster",
    0x02: "Zombie",
    0x03: "Warrior",
    0x04: "BeastWarrior",
    0x05: "Beast",
    0x06: "WingedBeast",
    0x07: "Fiend",
    0x08: "Fairy",
    0x09: "Insect",
    0x0A: "Dinosaur",
    0x0B: "Reptile",
    0x0C: "Fish",
    0x0D: "SeaSerpent",
    0x0E: "Machine",
    0x0F: "Thunder",
    0x10: "Aqua",
    0x11: "Pyro",
    0x12: "Rock",
    0x13: "Plant",
    0x14: "Magic",
    0x15: "Trap",
    0x16: "Ritual",
    0x17: "Equip",
}

TYPE_SOURCE_URL = "https://datacrystal.tcrf.net/wiki/Yu-Gi-Oh%21_Forbidden_Memories/Notes"
RULE_SOURCE_URL = "https://gamefaqs.gamespot.com/ps/561010-yu-gi-oh-forbidden-memories/faqs/78677"


@dataclass(frozen=True)
class Card:
    card_id: int
    name: str
    primary_type: str
    attack: int
    defense: int


@dataclass(frozen=True)
class Fusion:
    card_a_id: int
    card_b_id: int
    result_id: int
    origin: str


@dataclass(frozen=True)
class Rule:
    result_id: int
    type_a: str
    type_b: str
    material_a_ids: tuple[int, ...]
    material_b_ids: tuple[int, ...]
    origins: tuple[str, ...]

    @property
    def combination_count(self) -> int:
        return len(self.material_a_ids) * len(self.material_b_ids)


GroupKey = tuple[str, tuple[int, ...]]


def load_cards(path: pathlib.Path) -> dict[int, Card]:
    cards: dict[int, Card] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source, delimiter=";"):
            type_id = int(row["card_type"])
            if type_id not in CARD_TYPES:
                raise ValueError(f"Unknown card type ID {type_id} for card {row['card_id']}")
            card = Card(
                card_id=int(row["card_id"]),
                name=row["name"],
                primary_type=CARD_TYPES[type_id],
                attack=int(row["attack"]),
                defense=int(row["defense"]),
            )
            cards[card.card_id] = card
    if not cards:
        raise ValueError(f"No cards found in {path}")
    return cards


def load_fusions(path: pathlib.Path) -> list[Fusion]:
    fusions: list[Fusion] = []
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source, delimiter=";"):
            fusions.append(
                Fusion(
                    card_a_id=int(row["card_a_id"]),
                    card_b_id=int(row["card_b_id"]),
                    result_id=int(row["result_id"]),
                    origin=row["origin"],
                )
            )
    if not fusions:
        raise ValueError(f"No fusions found in {path}")
    return fusions


def build_rules(cards: dict[int, Card], fusions: list[Fusion]) -> list[Rule]:
    buckets: dict[tuple[int, str, str], list[Fusion]] = defaultdict(list)
    for fusion in fusions:
        type_a = cards[fusion.card_a_id].primary_type
        type_b = cards[fusion.card_b_id].primary_type
        first_type, second_type = sorted((type_a, type_b))
        buckets[(fusion.result_id, first_type, second_type)].append(fusion)

    rules: list[Rule] = []
    for (result_id, type_a, type_b), bucket in sorted(buckets.items()):
        neighbors: dict[int, set[int]] = defaultdict(set)
        edge_origins: dict[tuple[int, int], str] = {}
        for fusion in bucket:
            card_a = cards[fusion.card_a_id]
            if type_a == type_b or card_a.primary_type == type_a:
                material_a_id, material_b_id = fusion.card_a_id, fusion.card_b_id
            else:
                material_a_id, material_b_id = fusion.card_b_id, fusion.card_a_id
            neighbors[material_a_id].add(material_b_id)
            edge_origins[(material_a_id, material_b_id)] = fusion.origin

        rows_by_neighbor_set: dict[tuple[int, ...], set[int]] = defaultdict(set)
        for material_a_id, material_b_ids in neighbors.items():
            rows_by_neighbor_set[tuple(sorted(material_b_ids))].add(material_a_id)

        for material_b_ids, material_a_ids in rows_by_neighbor_set.items():
            sorted_a_ids = tuple(sorted(material_a_ids))
            origins = sorted(
                {
                    edge_origins[(material_a_id, material_b_id)]
                    for material_a_id in sorted_a_ids
                    for material_b_id in material_b_ids
                }
            )
            rules.append(
                Rule(
                    result_id=result_id,
                    type_a=type_a,
                    type_b=type_b,
                    material_a_ids=sorted_a_ids,
                    material_b_ids=material_b_ids,
                    origins=tuple(origins),
                )
            )
    return rules


def expanded_rule_fusions(rules: list[Rule]) -> set[tuple[int, int, int]]:
    expanded: set[tuple[int, int, int]] = set()
    for rule in rules:
        for card_a_id in rule.material_a_ids:
            for card_b_id in rule.material_b_ids:
                low_id, high_id = sorted((card_a_id, card_b_id))
                triple = (low_id, high_id, rule.result_id)
                if triple in expanded:
                    raise ValueError(f"Rules overlap on fusion {triple}")
                expanded.add(triple)
    return expanded


def validate_rules(rules: list[Rule], fusions: list[Fusion]) -> None:
    expected = {(item.card_a_id, item.card_b_id, item.result_id) for item in fusions}
    expanded = expanded_rule_fusions(rules)
    missing = expected - expanded
    extra = expanded - expected
    if missing or extra:
        raise ValueError(
            f"Rule reconstruction failed: missing={list(missing)[:10]}, extra={list(extra)[:10]}"
        )


def collect_group_keys(rules: list[Rule]) -> set[GroupKey]:
    keys: set[GroupKey] = set()
    for rule in rules:
        keys.add((rule.type_a, rule.material_a_ids))
        keys.add((rule.type_b, rule.material_b_ids))
    return keys


def assign_group_ids(group_keys: set[GroupKey]) -> dict[GroupKey, str]:
    by_type: dict[str, list[tuple[int, ...]]] = defaultdict(list)
    for primary_type, card_ids in group_keys:
        by_type[primary_type].append(card_ids)

    group_ids: dict[GroupKey, str] = {}
    for primary_type in sorted(by_type):
        groups = sorted(by_type[primary_type], key=lambda ids: (-len(ids), ids))
        prefix = "".join(character for character in primary_type.upper() if character.isalnum())
        for index, card_ids in enumerate(groups, 1):
            group_ids[(primary_type, card_ids)] = f"{prefix}-G{index:03d}"
    return group_ids


def group_condition(
    primary_type: str,
    card_ids: tuple[int, ...],
    cards: dict[int, Card],
) -> tuple[str, str, tuple[int, ...]]:
    if len(card_ids) == 1:
        return cards[card_ids[0]].name, "single_card", ()

    attacks = [cards[card_id].attack for card_id in card_ids]
    minimum, maximum = min(attacks), max(attacks)
    same_type_in_range = tuple(
        sorted(
            card.card_id
            for card in cards.values()
            if card.primary_type == primary_type and minimum <= card.attack <= maximum
        )
    )
    excluded = tuple(card_id for card_id in same_type_in_range if card_id not in card_ids)
    if set(same_type_in_range) == set(card_ids):
        label = f"All {primary_type}, ATK {minimum}-{maximum}"
        return label, "exact_type_and_atk_range", ()

    label = f"{primary_type} set ({len(card_ids)} cards, ATK {minimum}-{maximum})"
    return label, "explicit_subgroup", excluded


def rule_tier(combination_count: int) -> str:
    if combination_count >= 25:
        return "core"
    if combination_count >= 5:
        return "extended"
    if combination_count >= 2:
        return "small"
    return "exact"


def write_cards(path: pathlib.Path, cards: dict[int, Card]) -> None:
    fields = ["card_id", "name", "primary_type", "attack", "defense"]
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, delimiter=";")
        writer.writeheader()
        for card in sorted(cards.values(), key=lambda item: item.card_id):
            writer.writerow(
                {
                    "card_id": card.card_id,
                    "name": card.name,
                    "primary_type": card.primary_type,
                    "attack": card.attack,
                    "defense": card.defense,
                }
            )


def write_groups(
    path: pathlib.Path,
    members_path: pathlib.Path,
    group_keys: set[GroupKey],
    group_ids: dict[GroupKey, str],
    rules: list[Rule],
    cards: dict[int, Card],
) -> dict[GroupKey, dict[str, object]]:
    usage = Counter()
    for rule in rules:
        usage[(rule.type_a, rule.material_a_ids)] += 1
        usage[(rule.type_b, rule.material_b_ids)] += 1

    group_data: dict[GroupKey, dict[str, object]] = {}
    fields = [
        "group_id",
        "label",
        "primary_type",
        "card_count",
        "attack_min",
        "attack_max",
        "condition_kind",
        "rule_usage_count",
        "card_ids",
        "card_names",
        "same_type_cards_excluded_inside_atk_range",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, delimiter=";")
        writer.writeheader()
        for key in sorted(group_keys, key=lambda item: group_ids[item]):
            primary_type, card_ids = key
            label, condition_kind, excluded = group_condition(primary_type, card_ids, cards)
            attacks = [cards[card_id].attack for card_id in card_ids]
            data: dict[str, object] = {
                "group_id": group_ids[key],
                "label": label,
                "primary_type": primary_type,
                "card_count": len(card_ids),
                "attack_min": min(attacks),
                "attack_max": max(attacks),
                "condition_kind": condition_kind,
                "rule_usage_count": usage[key],
                "card_ids": ", ".join(map(str, card_ids)),
                "card_names": " | ".join(cards[card_id].name for card_id in card_ids),
                "same_type_cards_excluded_inside_atk_range": " | ".join(
                    f"{card_id} {cards[card_id].name}" for card_id in excluded
                ),
            }
            group_data[key] = data
            writer.writerow(data)

    member_fields = ["group_id", "label", "primary_type", "card_id", "card_name", "attack", "defense"]
    with members_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=member_fields, delimiter=";")
        writer.writeheader()
        for key in sorted(group_keys, key=lambda item: group_ids[item]):
            primary_type, card_ids = key
            data = group_data[key]
            for card_id in card_ids:
                card = cards[card_id]
                writer.writerow(
                    {
                        "group_id": group_ids[key],
                        "label": data["label"],
                        "primary_type": primary_type,
                        "card_id": card.card_id,
                        "card_name": card.name,
                        "attack": card.attack,
                        "defense": card.defense,
                    }
                )
    return group_data


def attack_status(rule: Rule, cards: dict[int, Card]) -> tuple[str, int]:
    result_attack = cards[rule.result_id].attack
    if result_attack == 0:
        return "result_has_zero_atk", rule.combination_count
    violations = sum(
        not (
            cards[card_a_id].attack < result_attack
            and cards[card_b_id].attack < result_attack
        )
        for card_a_id in rule.material_a_ids
        for card_b_id in rule.material_b_ids
    )
    return ("all_materials_below_result" if violations == 0 else "has_exceptions", violations)


def write_rules(
    path: pathlib.Path,
    json_path: pathlib.Path,
    rules: list[Rule],
    group_ids: dict[GroupKey, str],
    group_data: dict[GroupKey, dict[str, object]],
    cards: dict[int, Card],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    ordered_rules = sorted(
        rules,
        key=lambda item: (-item.combination_count, cards[item.result_id].name, item.material_a_ids),
    )
    for index, rule in enumerate(ordered_rules, 1):
        key_a = (rule.type_a, rule.material_a_ids)
        key_b = (rule.type_b, rule.material_b_ids)
        result = cards[rule.result_id]
        status, violation_count = attack_status(rule, cards)
        rows.append(
            {
                "rule_id": f"R{index:04d}",
                "tier": rule_tier(rule.combination_count),
                "material_a_group_id": group_ids[key_a],
                "material_a_label": group_data[key_a]["label"],
                "material_a_type": rule.type_a,
                "material_a_count": len(rule.material_a_ids),
                "material_a_attack_max": max(cards[item].attack for item in rule.material_a_ids),
                "material_b_group_id": group_ids[key_b],
                "material_b_label": group_data[key_b]["label"],
                "material_b_type": rule.type_b,
                "material_b_count": len(rule.material_b_ids),
                "material_b_attack_max": max(cards[item].attack for item in rule.material_b_ids),
                "result_id": result.card_id,
                "result_name": result.name,
                "result_type": result.primary_type,
                "result_attack": result.attack,
                "result_defense": result.defense,
                "combination_count": rule.combination_count,
                "attack_condition": status,
                "attack_exception_count": violation_count,
                "origin": ",".join(rule.origins),
            }
        )

    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return rows


def write_rule_subset(path: pathlib.Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def analyze_card_roles(
    cards: dict[int, Card],
    fusions: list[Fusion],
) -> list[dict[str, object]]:
    materials: set[int] = set()
    results: set[int] = set()
    outgoing: dict[int, set[int]] = defaultdict(set)
    reverse: dict[int, set[int]] = defaultdict(set)
    options: dict[int, list[tuple[int, int]]] = defaultdict(list)
    material_fusion_count = Counter()
    result_fusion_count = Counter()

    for fusion in fusions:
        results.add(fusion.result_id)
        result_fusion_count[fusion.result_id] += 1
        material_pairs = {(fusion.card_a_id, fusion.card_b_id), (fusion.card_b_id, fusion.card_a_id)}
        for material_id, partner_id in material_pairs:
            materials.add(material_id)
            outgoing[material_id].add(fusion.result_id)
            reverse[fusion.result_id].add(material_id)
            options[material_id].append((partner_id, fusion.result_id))
            material_fusion_count[material_id] += 1

    final_cards = results - materials
    distance_to_final = {card_id: 0 for card_id in final_cards}
    queue = deque(final_cards)
    while queue:
        result_id = queue.popleft()
        for material_id in reverse[result_id]:
            candidate_distance = distance_to_final[result_id] + 1
            if material_id not in distance_to_final or candidate_distance < distance_to_final[material_id]:
                distance_to_final[material_id] = candidate_distance
                queue.append(material_id)

    intermediate_cards = materials & results
    unreachable = sorted(intermediate_cards - distance_to_final.keys())
    if unreachable:
        raise ValueError(f"Intermediate cards cannot reach a final fusion: {unreachable[:20]}")
    invalid_levels = sorted(
        card_id for card_id in intermediate_cards if distance_to_final[card_id] not in {1, 2, 3}
    )
    if invalid_levels:
        details = [(card_id, distance_to_final[card_id]) for card_id in invalid_levels[:20]]
        raise ValueError(f"Intermediate levels exceed the expected 1..3 range: {details}")

    def representative_path(start_id: int) -> str:
        current_id = start_id
        parts = [cards[current_id].name]
        while distance_to_final[current_id] > 0:
            candidates = [
                (partner_id, result_id)
                for partner_id, result_id in options[current_id]
                if distance_to_final.get(result_id) == distance_to_final[current_id] - 1
            ]
            if not candidates:
                raise ValueError(f"No shortest-path fusion found for card {current_id}")
            partner_id, result_id = max(
                candidates,
                key=lambda item: (
                    cards[item[1]].attack,
                    cards[item[1]].defense,
                    -item[1],
                    -item[0],
                ),
            )
            parts.append(f"+ {cards[partner_id].name} -> {cards[result_id].name}")
            current_id = result_id
        return " ".join(parts)

    rows: list[dict[str, object]] = []
    for card in sorted(cards.values(), key=lambda item: item.card_id):
        is_material = card.card_id in materials
        is_result = card.card_id in results
        if is_material and not is_result:
            role = "material_inicial"
            role_pt = "Material inicial"
            remaining_levels: int | str = ""
        elif is_material and is_result:
            remaining_levels = distance_to_final[card.card_id]
            role = f"intermediaria_nivel_{remaining_levels}"
            role_pt = f"Intermediária - {remaining_levels} nível(is) até uma fusão final"
        elif is_result:
            role = "fusao_final"
            role_pt = "Fusão final"
            remaining_levels = 0
        else:
            role = "sem_participacao"
            role_pt = "Sem participação em fusões"
            remaining_levels = ""

        rows.append(
            {
                "card_id": card.card_id,
                "name": card.name,
                "primary_type": card.primary_type,
                "attack": card.attack,
                "defense": card.defense,
                "role": role,
                "role_pt_br": role_pt,
                "is_fusion_material": "yes" if is_material else "no",
                "is_fusion_result": "yes" if is_result else "no",
                "remaining_levels_to_final": remaining_levels,
                "fusion_count_as_material": material_fusion_count[card.card_id],
                "distinct_next_results": len(outgoing[card.card_id]),
                "fusion_count_as_result": result_fusion_count[card.card_id],
                "representative_shortest_path": (
                    representative_path(card.card_id) if is_material and is_result else ""
                ),
            }
        )
    return rows


def write_card_roles(
    csv_path: pathlib.Path,
    json_path: pathlib.Path,
    rows: list[dict[str, object]],
) -> None:
    with csv_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def write_size_distributions(
    output_dir: pathlib.Path,
    group_data: dict[GroupKey, dict[str, object]],
    rule_rows: list[dict[str, object]],
) -> dict[str, object]:
    group_counts = Counter(int(data["card_count"]) for data in group_data.values())
    group_memberships = Counter()
    for data in group_data.values():
        group_memberships[int(data["card_count"])] += int(data["card_count"])
    total_groups = len(group_data)
    total_memberships = sum(group_memberships.values())

    group_path = output_dir / "distribuicao_tamanho_grupos.csv"
    with group_path.open("w", encoding="utf-8-sig", newline="") as output:
        fields = [
            "tamanho_do_grupo",
            "quantidade_de_grupos",
            "percentual_dos_grupos",
            "total_de_membros_nesses_grupos",
            "percentual_das_matrizes_de_grupos",
        ]
        writer = csv.DictWriter(output, fieldnames=fields, delimiter=";")
        writer.writeheader()
        for size in sorted(group_counts):
            writer.writerow(
                {
                    "tamanho_do_grupo": size,
                    "quantidade_de_grupos": group_counts[size],
                    "percentual_dos_grupos": group_counts[size] / total_groups,
                    "total_de_membros_nesses_grupos": group_memberships[size],
                    "percentual_das_matrizes_de_grupos": group_memberships[size]
                    / total_memberships,
                }
            )

    rule_counts = Counter(int(row["combination_count"]) for row in rule_rows)
    rule_coverage = Counter()
    rule_tier_by_size: dict[int, str] = {}
    for row in rule_rows:
        size = int(row["combination_count"])
        rule_coverage[size] += size
        rule_tier_by_size[size] = str(row["tier"])
    total_rules = len(rule_rows)
    total_fusions = sum(rule_coverage.values())
    rule_path = output_dir / "distribuicao_tamanho_regras.csv"
    with rule_path.open("w", encoding="utf-8-sig", newline="") as output:
        fields = [
            "tamanho_da_regra_em_combinacoes",
            "quantidade_de_regras",
            "percentual_das_regras",
            "fusoes_cobertas",
            "percentual_das_fusoes",
            "faixa_da_regra",
        ]
        writer = csv.DictWriter(output, fieldnames=fields, delimiter=";")
        writer.writeheader()
        for size in sorted(rule_counts):
            writer.writerow(
                {
                    "tamanho_da_regra_em_combinacoes": size,
                    "quantidade_de_regras": rule_counts[size],
                    "percentual_das_regras": rule_counts[size] / total_rules,
                    "fusoes_cobertas": rule_coverage[size],
                    "percentual_das_fusoes": rule_coverage[size] / total_fusions,
                    "faixa_da_regra": rule_tier_by_size[size],
                }
            )

    grouped_count = sum(count for size, count in group_counts.items() if size > 1)
    rules_with_multiple_combinations = total_rules - rule_counts[1]
    summary_lines = [
        "# Distribuição dos tamanhos de grupos e regras",
        "",
        "## Tamanho dos grupos de materiais",
        "",
        f"Foram encontrados {total_groups} grupos de materiais.",
        f"{group_counts[1]} grupos ({group_counts[1] / total_groups:.1%}) são cartas individuais.",
        f"{grouped_count} grupos ({grouped_count / total_groups:.1%}) possuem duas ou mais cartas.",
        f"O maior grupo possui {max(group_counts)} cartas.",
        "",
        "| Tamanho | Grupos | Percentual |",
        "| ---: | ---: | ---: |",
    ]
    for size in sorted(group_counts):
        summary_lines.append(f"| {size} | {group_counts[size]} | {group_counts[size] / total_groups:.1%} |")
    summary_lines.extend(
        [
            "",
            "## Tamanho das regras de fusão",
            "",
            f"Foram encontrados {total_rules} regras, cobrindo {total_fusions} fusões.",
            f"{rule_counts[1]} regras ({rule_counts[1] / total_rules:.1%}) são fusões exatas de um par.",
            f"{rules_with_multiple_combinations} regras ({rules_with_multiple_combinations / total_rules:.1%}) representam grupos com duas ou mais combinações.",
            "",
            "| Combinações por regra | Regras | Fusões cobertas | Percentual das fusões |",
            "| ---: | ---: | ---: | ---: |",
        ]
    )
    for size in sorted(rule_counts, reverse=True):
        summary_lines.append(
            f"| {size} | {rule_counts[size]} | {rule_coverage[size]} | {rule_coverage[size] / total_fusions:.1%} |"
        )
    summary_lines.extend(
        [
            "",
            "Os dois CSVs desta análise mantêm os valores exatos para filtragem e ordenação.",
        ]
    )
    (output_dir / "distribuicao_tamanhos.md").write_text(
        "\n".join(summary_lines) + "\n", encoding="utf-8"
    )
    return {
        "group_size_distribution": dict(sorted(group_counts.items())),
        "rule_combination_size_distribution": dict(sorted(rule_counts.items())),
        "group_distribution_csv": str(group_path),
        "rule_distribution_csv": str(rule_path),
    }


def write_attack_exceptions(
    path: pathlib.Path,
    cards: dict[int, Card],
    fusions: list[Fusion],
) -> int:
    fields = [
        "card_a_id",
        "card_a_name",
        "card_a_type",
        "card_a_attack",
        "card_b_id",
        "card_b_name",
        "card_b_type",
        "card_b_attack",
        "result_id",
        "result_name",
        "result_attack",
        "origin",
        "reason",
    ]
    rows: list[dict[str, object]] = []
    for fusion in fusions:
        card_a = cards[fusion.card_a_id]
        card_b = cards[fusion.card_b_id]
        result = cards[fusion.result_id]
        if result.attack == 0:
            reason = "result_has_zero_atk"
        elif card_a.attack >= result.attack or card_b.attack >= result.attack:
            reason = "material_atk_not_below_result"
        else:
            continue
        rows.append(
            {
                "card_a_id": card_a.card_id,
                "card_a_name": card_a.name,
                "card_a_type": card_a.primary_type,
                "card_a_attack": card_a.attack,
                "card_b_id": card_b.card_id,
                "card_b_name": card_b.name,
                "card_b_type": card_b.primary_type,
                "card_b_attack": card_b.attack,
                "result_id": result.card_id,
                "result_name": result.name,
                "result_attack": result.attack,
                "origin": fusion.origin,
                "reason": reason,
            }
        )
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def write_guide(
    path: pathlib.Path,
    rule_rows: list[dict[str, object]],
    group_data: dict[GroupKey, dict[str, object]],
) -> None:
    usage_order = sorted(
        group_data.values(),
        key=lambda item: (-int(item["rule_usage_count"]), -int(item["card_count"]), str(item["group_id"])),
    )
    core_rules = [row for row in rule_rows if row["tier"] == "core"]
    lines = [
        "# Fusion Pattern Memorization Guide",
        "",
        "This guide is generated from the mod's effective fusion table.",
        "Every rule is exact: expanding all rule set products reconstructs all 9,020 fusions.",
        "",
        "## How to read",
        "",
        "`Group A + Group B = Result` means every card in A fuses with every card in B",
        "to produce that result. Use `material_groups.csv` for complete group membership.",
        "",
        "## Most reusable material groups",
        "",
    ]
    for group in usage_order[:30]:
        lines.append(
            f"- {group['group_id']} - {group['label']}; used in {group['rule_usage_count']} rules; "
            f"members: {group['card_names']}"
        )
    lines.extend(["", "## Core rules (25 or more combinations)", ""])
    for row in core_rules:
        lines.append(
            f"- {row['rule_id']}: {row['material_a_group_id']} ({row['material_a_label']}) + "
            f"{row['material_b_group_id']} ({row['material_b_label']}) = "
            f"{row['result_name']} ({row['result_attack']}/{row['result_defense']}); "
            f"{row['combination_count']} combinations"
        )
    lines.extend(
        [
            "",
            "## Sources and method",
            "",
            f"- Card type ID mapping: {TYPE_SOURCE_URL}",
            f"- General-rule, secondary-type and ATK-threshold model: {RULE_SOURCE_URL}",
            "- The sources describe the original game. Rule membership and results here are learned",
            "  and validated against this mod's extracted data, not copied from the original game.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def portuguese_group_label(label: object) -> str:
    text = str(label)
    if text.startswith("All "):
        text = "Todos os " + text[4:]
    if " set (" in text:
        primary_type, details = text.split(" set (", 1)
        text = f"Conjunto {primary_type} ({details}"
    return text.replace(" cards,", " cartas,").replace(" card,", " carta,")


def write_guide_pt_br(
    path: pathlib.Path,
    rule_rows: list[dict[str, object]],
    group_data: dict[GroupKey, dict[str, object]],
    role_rows: list[dict[str, object]],
) -> None:
    usage_order = sorted(
        group_data.values(),
        key=lambda item: (-int(item["rule_usage_count"]), -int(item["card_count"]), str(item["group_id"])),
    )
    role_order = [
        "material_inicial",
        "intermediaria_nivel_1",
        "intermediaria_nivel_2",
        "intermediaria_nivel_3",
        "fusao_final",
        "sem_participacao",
    ]
    rows_by_role: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in role_rows:
        rows_by_role[str(row["role"])].append(row)

    labels = {
        "material_inicial": "Materiais iniciais",
        "intermediaria_nivel_1": "Intermediárias - 1 nível até uma fusão final",
        "intermediaria_nivel_2": "Intermediárias - 2 níveis até uma fusão final",
        "intermediaria_nivel_3": "Intermediárias - 3 níveis até uma fusão final",
        "fusao_final": "Fusões finais",
        "sem_participacao": "Cartas sem participação em fusões",
    }
    definitions = {
        "material_inicial": "É material de fusão, mas nunca aparece como resultado.",
        "intermediaria_nivel_1": "É resultado e material; existe uma rota de mais 1 fusão até uma carta final.",
        "intermediaria_nivel_2": "É resultado e material; a menor rota até uma carta final usa mais 2 fusões.",
        "intermediaria_nivel_3": "É resultado e material; a menor rota até uma carta final usa mais 3 fusões.",
        "fusao_final": "É resultado de fusão e não serve como material em nenhuma outra fusão.",
        "sem_participacao": "Não aparece como material nem como resultado na tabela efetiva.",
    }

    lines = [
        "# Guia de memorização de fusões",
        "",
        "Este guia foi gerado a partir da tabela efetiva do mod.",
        "Os `primary types` das cartas permanecem em inglês.",
        "",
        "## Como ler as regras",
        "",
        "`Conjunto A + Conjunto B = Resultado` significa que toda carta de A funde com",
        "toda carta de B para produzir o mesmo resultado. A lista completa dos membros",
        "continua em `material_groups.csv`.",
        "",
        "## Papéis das cartas nas cadeias",
        "",
        "Para cartas intermediárias, o nível é a menor quantidade de fusões adicionais",
        "necessária para alcançar uma carta que não serve mais como material.",
        "Quando existem várias rotas, mostramos uma rota curta representativa.",
        "",
        "| Categoria | Cartas | Definição |",
        "| --- | ---: | --- |",
    ]
    for role in role_order:
        lines.append(f"| {labels[role]} | {len(rows_by_role[role])} | {definitions[role]} |")

    lines.extend(["", "## Conjuntos de materiais mais reutilizados", ""])
    for group in usage_order[:30]:
        lines.append(
            f"- {group['group_id']} - {portuguese_group_label(group['label'])}; "
            f"usado em {group['rule_usage_count']} regras; membros: {group['card_names']}"
        )

    core_rules = [row for row in rule_rows if row["tier"] == "core"]
    lines.extend(["", "## Regras principais (25 ou mais combinações)", ""])
    for row in core_rules:
        lines.append(
            f"- {row['rule_id']}: {row['material_a_group_id']} "
            f"({portuguese_group_label(row['material_a_label'])}) + "
            f"{row['material_b_group_id']} ({portuguese_group_label(row['material_b_label'])}) = "
            f"{row['result_name']} ({row['result_attack']}/{row['result_defense']}); "
            f"{row['combination_count']} combinações"
        )

    for role in role_order:
        role_rows_sorted = sorted(
            rows_by_role[role],
            key=lambda row: (str(row["primary_type"]), int(row["attack"]), int(row["card_id"])),
        )
        lines.extend(["", f"## {labels[role]} ({len(role_rows_sorted)})", "", definitions[role], ""])
        current_type = None
        for row in role_rows_sorted:
            if row["primary_type"] != current_type:
                current_type = row["primary_type"]
                lines.extend(["", f"### {current_type}", ""])
            route = (
                f"; rota curta: {row['representative_shortest_path']}"
                if row["representative_shortest_path"]
                else ""
            )
            lines.append(
                f"- ID {row['card_id']} - {row['name']} ({row['attack']}/{row['defense']}){route}"
            )

    lines.extend(
        [
            "",
            "## Fontes e método",
            "",
            f"- Mapeamento dos primary types: {TYPE_SOURCE_URL}",
            f"- Modelo de regras, tipos secundários e limites de ATK: {RULE_SOURCE_URL}",
            "- As fontes descrevem o jogo original. Os papéis, níveis, conjuntos e resultados",
            "  deste guia foram calculados e validados diretamente a partir deste mod.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compress effective fusion pairs into exact material-set rules.")
    parser.add_argument("cards_csv", type=pathlib.Path)
    parser.add_argument("fusions_csv", type=pathlib.Path)
    parser.add_argument("--output-dir", type=pathlib.Path, default=pathlib.Path("exports/fusion_patterns"))
    args = parser.parse_args()

    cards = load_cards(args.cards_csv)
    fusions = load_fusions(args.fusions_csv)
    rules = build_rules(cards, fusions)
    validate_rules(rules, fusions)
    group_keys = collect_group_keys(rules)
    group_ids = assign_group_ids(group_keys)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_cards(args.output_dir / "cards_gameplay.csv", cards)
    group_data = write_groups(
        args.output_dir / "material_groups.csv",
        args.output_dir / "material_group_members.csv",
        group_keys,
        group_ids,
        rules,
        cards,
    )
    rule_rows = write_rules(
        args.output_dir / "fusion_rules.csv",
        args.output_dir / "fusion_rules.json",
        rules,
        group_ids,
        group_data,
        cards,
    )
    write_rule_subset(
        args.output_dir / "fusion_rules_core.csv",
        [row for row in rule_rows if row["tier"] == "core"],
    )
    write_rule_subset(
        args.output_dir / "fusion_rules_memorizable.csv",
        [row for row in rule_rows if row["tier"] in {"core", "extended"}],
    )
    attack_exception_count = write_attack_exceptions(
        args.output_dir / "fusion_attack_exceptions.csv", cards, fusions
    )
    write_guide(args.output_dir / "memorization_guide.md", rule_rows, group_data)
    role_rows = analyze_card_roles(cards, fusions)
    write_card_roles(
        args.output_dir / "card_fusion_roles.csv",
        args.output_dir / "card_fusion_roles.json",
        role_rows,
    )
    write_guide_pt_br(
        args.output_dir / "guia_memorizacao_pt_br.md",
        rule_rows,
        group_data,
        role_rows,
    )
    size_distributions = write_size_distributions(args.output_dir, group_data, rule_rows)

    tier_counts = Counter(str(row["tier"]) for row in rule_rows)
    tier_coverage = Counter()
    for row in rule_rows:
        tier_coverage[str(row["tier"])] += int(row["combination_count"])
    nonzero_result_fusions = sum(cards[fusion.result_id].attack != 0 for fusion in fusions)
    strict_atk_count = sum(
        cards[fusion.result_id].attack != 0
        and cards[fusion.card_a_id].attack < cards[fusion.result_id].attack
        and cards[fusion.card_b_id].attack < cards[fusion.result_id].attack
        for fusion in fusions
    )
    summary = {
        "cards": len(cards),
        "effective_fusions": len(fusions),
        "exact_rules": len(rules),
        "unique_material_groups": len(group_keys),
        "rule_tiers": dict(tier_counts),
        "fusion_coverage_by_tier": dict(tier_coverage),
        "core_rule_coverage_rate": tier_coverage["core"] / len(fusions),
        "core_plus_extended_coverage_rate": (
            tier_coverage["core"] + tier_coverage["extended"]
        )
        / len(fusions),
        "nonzero_attack_result_fusions": nonzero_result_fusions,
        "strict_attack_rule_fusions": strict_atk_count,
        "strict_attack_rule_rate_among_nonzero_results": strict_atk_count
        / nonzero_result_fusions,
        "nonzero_result_attack_rule_violations": nonzero_result_fusions - strict_atk_count,
        "attack_exception_rows_including_zero_atk_results": attack_exception_count,
        "card_fusion_roles": dict(Counter(str(row["role"]) for row in role_rows)),
        "size_distributions": size_distributions,
        "validation": "all rules expand to exactly the effective fusion table",
        "sources": [TYPE_SOURCE_URL, RULE_SOURCE_URL],
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
