# Equipment Compatibility Investigation

Date: 2026-07-17

## Goal

Extract the exact set of Equip cards accepted by every monster in the
`Yu-Gi-Oh! Remastered Perfected (Drop x15)` ROM.

## Confirmed controls

- ID 690: `Fake Trap` (Trap).
- ID 693: `Contruct of Mask` (Ritual).
- ID 695: `Puppet Ritual` (Ritual).
- Monster samples selected for differential tests: 96 (`Little D`), 56
  (`Harpie Lady`), 126 (`Water Omotics`), 1 (`Baby Dragon`), 11 (`Lord Of D.`),
  and 36 (`Celtic Guardian`).
- Validated compatibility signature supplied from gameplay: `Baby Dragon`
  (ID 1) accepts exactly IDs `305`, `308`, `313`, `315`, `327`, `657` and
  `668` (`Laser Cannon Armor`, `Beast Fangs`, `Horn of Light`, `Dragon
  Treasure`, `Magicians Robe`, `Megamorph` and `Bright Castle`).

## Ruled-out locations

1. The fusion table in `DATA/WA_MRG.MRG` at `0x00B87800` is not the generic
   equipment-compatibility table. It contains only 75 special fusions involving
   Equip cards, such as character-specific transformation recipes.
2. The `SLUS_014.11` table at `0x001C558C` is not a per-card Equip list. The
   three controls contain the sentinel `0x6000`, and monster rows are card-ID
   permutations with no compatibility signal.
3. `SLUS_014.11` references near `0x801C0000` inspected in the executable are
   resource-loading code, not duel/equipment logic.

## Card metadata layout checked

The primary card metadata is in `SLUS_014.11` and was checked as a contiguous
region, rather than as unrelated offsets:

- `0x001C4A44`: 722 packed 32-bit records, containing ATK, DEF, guardian stars
  and card type.
- `0x001C558C`: 722 16-bit values. It is a complete permutation of `0..722`,
  so it is an index/order mapping rather than an equipment-compatibility field.
- `0x001C5B33`: 722 bytes, containing level and attribute.
- `0x001C5E05..0x001C6001`: zero-filled padding.
- `0x001C6002`: name pointers, followed by encoded card names.

All Equip cards have zeroed ATK/DEF/guardian-star/level fields and the same
attribute value (`6`), so the compatibility data is not encoded in those card
record fields. The explicit `card_type == Equip (23)` branch at runtime
`0x8001E634` was also inspected: it selects a UI/action state and does not
validate a target monster.

## Encoding tests using Baby Dragon

The validated seven-ID set does not occur in either `SLUS_014.11` or
`DATA/WA_MRG.MRG` as any of the following direct encodings:

- a 37-bit mask indexed by the mod's Equip cards (both bit orders and byte
  orders);
- a 722-bit mask indexed by card ID (both zero/one-based indexing, bit orders
  and byte orders);
- a contiguous 10-bit packed ID list, in forward/reverse order and zero/one-
  based variants.

This rules out a direct per-card compatibility matrix in the extracted files.
The next extraction must locate the routine or an indirect, transformed table
used when an Equip is applied.

## Original-rule validation

The public original-game equipment guide lists original `#004 Baby Dragon` with
the exact seven functional IDs validated in this mod: `305`, `308`, `313`,
`315`, `327`, `657`, and `668`. In the original, ID `327` is named `Follow
Wind`; the mod displays that ID as `Magicians Robe`. This is strong evidence
that the mod preserves the original equipment behavior by functional card ID,
even where its display names changed.

Source: https://gamefaqs.gamespot.com/ps/561010-yu-gi-oh-forbidden-memories/faqs/25888

The target-to-original identity mapping is not a direct 722-entry little-
endian table in either extracted `SLUS_014.11` or `WA_MRG.MRG`; an anchor scan
using 305 uniquely matched display names found no such vector. The remaining
target is therefore the transformed lookup used by the duel code or a packed
resource table.

## Public evidence

- The original game's ROM map documents the SLUS layout and the fusion lookup,
  but does not document a generic equipment compatibility table:
  https://datacrystal.tcrf.net/wiki/Yu-Gi-Oh%21_Forbidden_Memories/ROM_map
- Public compatibility guides apply to the original card roster only. This mod
  changes card IDs and includes changed/replaced cards, so those lists are not
  valid output for this catalog without runtime validation.

## Exact routine and table located

The equipment lookup routine is in `SLUS_014.11` at file offset `0x0000A208`
(runtime `0x80019A08`). After a normal fusion fails, the caller at runtime
`0x8001A344` invokes this routine and then retries with the two card IDs
reversed. The routine reads a variable-length table loaded at RAM
`0x8017A1D8`:

1. `u16 equip_id`
2. `u16 accepted_card_count`
3. `accepted_card_count` little-endian `u16` card IDs
4. Repeat until a zero `equip_id` sentinel

The corresponding source table is in `DATA/WA_MRG.MRG` at file offset
`0x00B85000`. It contains all 37 Equip IDs in this mod, including the new IDs
338, 339 and 340, and ends at the sentinel at `0x00B869B2`. There are 3,215
exact compatibility relations. At least one Equip record references 516 of the
mod's 622 monster-type cards. IDs 496 and above are absent specifically from
the 445-entry lists for IDs 657 (`Megamorph`) and 668 (`Bright Castle`). All six
executable call sites for the lookup routine use this same table, so this
exclusion is behavior encoded by the mod rather than an extractor fallback.

The modified ROM itself lists five compatible equips for card ID 1 Baby
Dragon: `308`, `313`, `315`, `657`, and `668`. Unlike the original-game guide,
this mod's table does not include `305` or `327` for Baby Dragon. This is
consistent with the changed function of ID 327 (`Magicians Robe` instead of
the original `Follow Wind`) and shows why original-game lists cannot be used
as the final source of truth for the mod.
