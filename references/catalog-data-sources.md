# Fontes dos dados do catálogo

`tools/build_catalog_data.py` gera `catalogo/data.js`, copiado para `catalogo_publico/public/catalogo/data.js` antes da publicação.

## Cartas dos mods

Para cada conjunto (`exports/`, `exports/naruto/` e `exports/naruto_shippuden_final/`), os campos vêm de `fusions/cards.csv`: `card_id`, `name`, `attack`, `defense`, `guardian_star_1`, `guardian_star_2`, `card_type`, `level` e `attribute`.

Esse CSV é extraído de `SLUS_014.11` (ou do executável correspondente de cada mod) por `tools/extract_fusions.py`. Offsets: `0x001C4A44` para estatísticas compactadas, `0x001C5B33` para nível/atributo e `0x001C6002` para ponteiros de nome, com viés `0x001C0800`.

## Descrições — fonte autoritativa dos mods

As descrições são extraídas diretamente dos executáveis dos mods, nunca de uma base do jogo original nem de sites externos:

| Dataset | Executável |
| --- | --- |
| `remastered` | `extracted/SLUS_014.11` |
| `naruto` | `extracted_naruto/SLUS_025.11` |
| `naruto_shippuden_final` | `extracted_naruto_shippuden_final/SLUS_096.11` |

Em todos os três executáveis, a tabela contém 723 ponteiros `uint16le` em `0x001B0A00`. A entrada zero é reservada; a carta de ID `n` usa o ponteiro na posição `n`, em `0x001B0A00 + n * 2`. O endereço do texto é `0x001B0800 + ponteiro`. Os bytes são decodificados por `references/chartable.tbl`, `0xFF` encerra a string e `0xFE` representa quebra de linha.

Validações de referência:

- Remastered ID 301, United We Stand: `Motivates warriors in order to make them stronger!`
- Remastered ID 492, Yubel - Terror Incarnate: `One of three malicious spirits that have sworn to protect the tomb of anubis`
- Naruto ID 301: `Poder solo disponible para Jinchurikis.`

Essas evidências também demonstram que as descrições são personalizadas por mod e não devem ser associadas por nome ou ID ao jogo original.

O Remastered e o Naruto têm texto para as 722 cartas. No Naruto Shippuden Final, 209 entradas apontam para texto vazio no executável; o catálogo preserva essas ausências em vez de completar com dados de outro jogo ou mod.

## Outros dados

| Dado | Arquivo exportado |
| --- | --- |
| Fusões | `fusions/fusions_effective.csv` |
| Drops | `drops/drop_rates.csv` |
| Decks | `opponent_decks/opponent_deck_rates.csv` |
| Equipamentos | `equipment/equipment_compatibility.csv` |

Os CSVs preservam offsets quando aplicável: `absolute_wa_mrg_offset` para fusões, `wa_mrg_offset` para drops/decks e `record_offset` para equipamentos. As tabelas correspondentes estão em `DATA/WA_MRG.MRG`.
