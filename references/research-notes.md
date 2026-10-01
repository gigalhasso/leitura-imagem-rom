# Research Notes

## 2026-07-12 - Initial Fusion/Card-ID Research

Question: where should we look for fusion tables and card IDs in the PS1 ROM?

Local findings:

- `SLUS_014.11` contains a contiguous `uint16le` table at file offset `0x001C558C`.
- The table has `723` values and is a perfect permutation of `0..722`.
- Since public gameplay references consistently describe Forbidden Memories as having `722` cards, this is very likely a card-ID ordering/shuffle table or card-index helper table.
- This is not yet proven to be the fusion table.

Useful commands:

```powershell
& "C:\Users\fimal\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" tools\find_u16_permutations.py extracted\SLUS_014.11 --max-value 722
& "C:\Users\fimal\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" tools\find_candidate_tables.py extracted\SLUS_014.11 extracted\DATA\SU.MRG --min-records 24 --limit 60 --record-sizes 6 --fields 3
```

Public sources:

- GameFAQs guide index for the PlayStation game lists multiple fusion/card guides, including a 2020 Fusion Guide and older Fusion FAQ/Card Password guides: https://gamefaqs.gamespot.com/ps/561010-yu-gi-oh-forbidden-memories/faqs
- TuringMachine's Fusion Guide says it covers all `50242` fusions and explains that it was generated/validated from databases including `FmDatabase.db` and `FmDatabaseWithGS.db`: https://gamefaqs.gamespot.com/ps/561010-yu-gi-oh-forbidden-memories/faqs/78677
- GameFAQs trivia notes that players hacked the game and verified certain unobtainable cards are not in opponent drop lists, supporting the idea that public reverse-engineering/data-dump work exists for drops/card data: https://gamefaqs.gamespot.com/ps/561010-yu-gi-oh-forbidden-memories/faqs

Next local experiments:

1. Search for references/pointers to file offset `0x001C558C` as a PS1 memory address.
2. Search for other `uint16le` arrays of length `723`, and for arrays with `722` records.
3. Use known fusion/card data from public guides only as validation targets, not as a replacement for ROM extraction.
4. Look for `FmDatabase.db` or related tooling publicly; if found, compare its IDs/fusions to candidate binary structures.

Follow-up:

- PS-X EXE header indicates load destination `0x80010000`, payload size `0x001D0000`, and entry PC `0x800129D8`.
- File offset `0x001C558C` maps to RAM address `0x801D4D8C` if using `dest + (file_offset - 0x800)`.
- Direct little-endian pointer search for `0x801D4D8C` found no hits in `SLUS_014.11`.
- Simple MIPS `lui` + immediate reference search for `0x801D4D8C` also found no hits.
- Current inference: this table may be reached through a nearby base pointer or by positional access inside a larger data block.

Card stat search:

- Public card/password guide gives stable card IDs and stats, for example card `001` Blue Eyes White Dragon is `3000/2500`, card `016` Time Wizard is `500/400`, card `069` Thousand Dragon is `2400/2000`.
- Exact search for the first known ATK/DEF sequence in `SLUS_014.11` and `DATA/SU.MRG` found no hits.
- Exact search for individual `uint16le` ATK/DEF pairs such as `3000,2500`, `500,400`, `2400,2000`, `4500,3800` also found no hits in those files.
- Current inference: card stats are not stored as plain consecutive little-endian `uint16` pairs in these two files, or the relevant table is encoded/compressed/ordered with additional transformation.

## 2026-07-13 - Fusion Table Format Confirmed

Question: where is the mod's fusion table, and how is it encoded?

Short answer:

- The fusion table is in `DATA/WA_MRG.MRG` at offset `0x00B87800`.
- The first 723 `uint16le` values are offsets indexed by card ID; entry zero is unused.
- Each card list starts with a compact count and then stores two `(material, result)` pairs in every five-byte block.
- The first byte of each block contains the two high bits of all four IDs. The remaining four bytes contain their low eight bits.

Sources:

- https://datacrystal.tcrf.net/wiki/Yu-Gi-Oh%21_Forbidden_Memories/ROM_map - documents the `SLUS-01411` fusion-checking routine, offset index, five-byte packing, and odd-list glitch behavior.
- https://github.com/vishtheshnu/forbidden-memories-fusion-finder - public extractor that reads fusion data from `WA_MRG.MRG` at `0xB87800` and card metadata from `SLUS_014.11`.
- https://raw.githubusercontent.com/vishtheshnu/forbidden-memories-fusion-finder/master/filereader.py - concrete Python implementation and table offsets used as a reproducible cross-check.

Verified local findings:

- All 722 fusion pointers and all decoded IDs pass bounds/range validation.
- The mod contains 9,174 declared records and 9,136 unique declared triples.
- Exhaustively emulating the game's lookup routine produces 9,020 effective fusions.
- Of the declared rows, 9,045 return their declared result, 127 are shadowed by an earlier result, and two use a reversed pair that the routine cannot reach after sorting the inputs.
- Thirty-eight effective declared rows are duplicate records. The 9,045 effective declared rows reduce to 9,007 unique declared combinations; adding 13 odd-list glitch fusions produces 9,020 effective combinations.
- The odd-list bug creates 13 effective glitch fusions in this mod. The public ROM map reports 15 for the original game, so the difference is compatible with modified table contents.
- Known behavior validates the result: mod ID 1 `Baby Dragon` plus mod ID 12 `Time Wizard` returns mod ID 219 `Thousand Dragon`.

Important compatibility finding:

- This mod does not preserve the original game's card-ID mapping.
- Examples from the mod's own card table: `Time Wizard` is ID 12; `Blue-Eyes White Dragon` appears at IDs 199, 468, and 469; additional/remastered cards are present.
- Therefore, original-game IDs cannot be used directly to search this mod's binary. Names and stats must be extracted from this mod's `SLUS_014.11`.

## 2026-07-14 - Opponent Drop Tables Confirmed

Question: where are the card-drop rates for every opponent and victory rank in the mod?

Short answer:

- `DATA/WA_MRG.MRG` stores 39 duelist blocks starting at `0xE9B000`, with a stride of `0x1800` bytes.
- Each block contains three 722-entry little-endian `uint16` drop tables: `S/A POW` at `+0x5B4`, `B/C/D POW/TEC` at `+0xB68`, and `S/A TEC` at `+0x111C`.
- Every one of the mod's 117 pools sums exactly to 2,048.

Sources:

- https://github.com/forbidden-memories-coding/fmlib-cpp/blob/master/FMLib/FMLib/src/DataReader.cpp - reads 39 duelists from `0xE9B000 + 0x1800 * i` and the three drop arrays at offsets `0x5B4`, `0xB68`, and `0x111C`.
- https://datacrystal.tcrf.net/wiki/Yu-Gi-Oh%21_Forbidden_Memories/ROM_map - documents the card-drop routine, 722 `uint16` probabilities, the `PRNG & 2047` selection, and cumulative lookup.
- https://www.speedrun.com/yugiohfm/guides/o9dax - documents the rank-to-pool mapping: S/A-POW, B/C/D-POW or TEC, and S/A-TEC, with probabilities expressed over 2,048.

Verified local findings:

- Duelist names are read from the mod's `SLUS_014.11`; all 39 names decode successfully.
- There are 117 valid drop pools and 84,474 audited duelist/pool/card cells.
- The extractor rejects the data if any pool does not sum to 2,048, preventing a wrong offset or incompatible layout from producing plausible-looking output.
- Probabilities exported by `tools/extract_drops.py` are per card-selection draw. The Drop x15 patch changes the reward count, while the pool weights remain stored as `x/2048`.

## 2026-07-14 - Opponent Deck Pools Confirmed

Question: which cards can each opponent use, and what are their generation weights?

Short answer:

- The first 722-entry `uint16` table in each duelist block is the opponent's single deck pool.
- Its offset is `0xE9B000 + 0x1800 * duelist_index` in `DATA/WA_MRG.MRG`.
- All 39 deck pools in this mod sum exactly to 2,048.

Sources:

- https://github.com/forbidden-memories-coding/fmlib-cpp/blob/master/FMLib/FMLib/src/DataReader.cpp - labels the first table in each duelist block as `Deck` and reads all 722 weights before the three drop pools.
- https://datacrystal.tcrf.net/wiki/Yu-Gi-Oh%21_Forbidden_Memories/ROM_map - documents weighted card selection using a PRNG masked to `0x07FF`, cumulative card probabilities, a three-copy limit during deck construction, and the later shuffle of a 40-card deck.

Verified local findings:

- The mod contains 39 valid opponent deck pools and 28,158 audited duelist/card cells.
- Every pool totals exactly 2,048, providing a strong offset and layout validation.
- `tools/extract_opponent_decks.py` exports the raw generation weight, percentage per selection attempt, card identity from the mod's own `SLUS_014.11`, and exact `WA_MRG.MRG` offset.
- The raw `x/2048` value is a deck-generation weight. The exact chance of drawing a card on a particular turn also depends on the generated 40-card deck and its shuffle order.

Project changes:

- Added `tools/extract_fusions.py` to decode cards, declared fusion records, and effective game behavior.
- Added `references/chartable.tbl`, sourced from the public fusion-finder repository, to decode names.
- Generated semicolon-delimited outputs under `exports/fusions/`.

Confidence: high. The public routine description, independent public extractor, binary structure, ID ranges, card names/stats, and a known fusion all agree.

## 2026-07-14 - Card Types and Exact Fusion Rule Induction

Question: can the mod's 9,020 effective fusions be compressed into memorable groups based on card type, ATK and explicit subgroups?

Short answer:

- Yes. The effective table can be represented exactly by 627 set-product rules.
- The 79 largest rules cover 6,300 fusions (69.8%).
- The 246 rules with at least five combinations cover 8,444 fusions (93.6%).
- The remaining long tail is 156 small rules and 225 exact one-pair fusions.

Sources:

- https://datacrystal.tcrf.net/wiki/Yu-Gi-Oh%21_Forbidden_Memories/Notes - maps internal type IDs `00..17` to Dragon, Spellcaster, Zombie, Warrior, BeastWarrior, Beast, WingedBeast, Fiend, Fairy, Insect, Dinosaur, Reptile, Fish, SeaSerpent, Machine, Thunder, Aqua, Pyro, Rock, Plant, Magic, Trap, Ritual and Equip.
- https://gamefaqs.gamespot.com/ps/561010-yu-gi-oh-forbidden-memories/faqs/78677 - documents the original game's general-rule model, secondary card types, conflict precedence and the usual strict material-ATK-below-result requirement.

Method:

- Each effective fusion is partitioned by result and unordered pair of primary types.
- Within each partition, material-A cards with identical material-B result neighborhoods are grouped together.
- This produces exact Cartesian products `A x B = result`, not probabilistic clusters.
- Re-expanding every product is required to reproduce the effective fusion table exactly with no missing, extra or overlapping triples.
- Material groups are labelled with their primary type and ATK range when that is exact. Otherwise their explicit card membership is retained as a behavioral subgroup.

Local findings:

- 722 cards were mapped to English primary-type names, ATK and DEF.
- 627 exact rules use 392 distinct material groups.
- Rule tiers: 79 core, 167 extended, 156 small and 225 exact.
- Of 9,011 fusions with a nonzero-ATK result, 8,989 (99.76%) have both materials strictly below the result's ATK.
- There are 22 nonzero-result ATK exceptions plus nine fusions whose result has zero ATK.
- The most reused group is `{Time Wizard, Time Wizard Of Tomorrow}`, used in 78 rules.
- Large reusable groups include ten low-ATK Dragons, ten low-ATK Fiends, ten low-ATK Warriors, ten low-ATK Plants and similar type-specific sets.

Project changes:

- Added `tools/analyze_fusion_patterns.py`.
- Generated card, group, rule, exception, JSON and memorization-guide outputs under `exports/fusion_patterns/`.

Confidence: high for extracted types, stats, memberships and rule coverage because the set products are checked against every effective fusion. Medium for human-facing subgroup names because they are descriptive labels, not names stored by the game.

### Fusion-chain role classification

- Material only / never a result: 204 cards.
- Result and material, shortest distance 1 to a terminal fusion: 142 cards.
- Result and material, shortest distance 2: 18 cards.
- Result and material, shortest distance 3: one card (`Bracchio-raidus`).
- Result only / terminal fusion: 76 cards.
- Neither material nor result: 281 cards.
- All 161 intermediate cards can reach a terminal fusion in at most three steps along a shortest path.
- The Portuguese guide records one representative shortest path for every intermediate card.

## 2026-07-14 - Card Sprite Extraction Investigation

Question: can card sprites be decoded directly from the Remastered Perfected files without running an emulator?

Verified local findings:

- `DATA/SU.MRG` is byte-identical between `Yu-Gi-Oh! Mod 15 (Drop x1)` and Remastered Perfected. Modified visual data is therefore in `DATA/WA_MRG.MRG`.
- `WA_MRG.MRG` differs in 5,855 sectors. An early diff showed extensive changes through approximately `0x9DF000`, but that value is not the start or end of the card-image region and must not be used as a layout boundary.
- A card/model routine in `SLUS_014.11` multiplies a normalized monster index by `0x114` and reads from `M:/mrgSU/model.mrg`. This is the monster-model resource path, not the remastered card-art path, because `SU.MRG` is unchanged.
- The earlier `0x3800` tests started at file offset zero and therefore did not test the card records. Publicly preserved Hack Suite source identifies the actual card region at `WA_MRG.MRG + 0x169000`.
- There are 722 fixed card records of `0x3800` bytes. Record index zero is card ID 1. Each record contains a 102x96 8-bpp image plus a 256-color ABGR1555 palette, a 96x14 4-bpp name bitmap, and a 40x32 8-bpp mini image plus its own palette.
- `tools/extract_card_images.py` implements this layout. It was visually validated on Remastered (Baby Dragon, Blue-Eyes White Dragon, and card 722) and Naruto files.

Public evidence:

- https://lanee.blog.fc2.com/blog-entry-207.html documents a historical visualizer that reads `SU.MRG`, `SLUS_014.11`, `WA_MRG.MRG`, and `MODEL.MRG`, but no archived package or source was recoverable.
- https://olhodomilenio.com/ provides a public mod catalog. Its site code uses `https://api.olhodomilenio.com/v1/`, but the direct API returned HTTP 406 from this environment, so it could not provide a sprite export.

Project changes:

- Added `tools/compare_sector_diffs.py`, `tools/find_monotonic_offset_tables.py`, `tools/render_indexed_test.py`, and `tools/discover_olm_catalog.py` for reproducible comparison and bounded follow-up work.
- Added `extracted/reference_mod15/` and `exports/reference_mod15/cards.csv` as the original-art comparison baseline.

Recommended next route:

- Capture one known card texture from a controlled emulator session, preferably Blue-Eyes White Dragon ID 199. The capture can establish the palette and layout needed to turn the already-located `WA_MRG.MRG` data into PNGs. This is the first remaining route that requires foreground emulator/keyboard interaction.
