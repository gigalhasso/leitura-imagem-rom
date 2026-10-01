# Opponent portrait images

## Confirmed location and format

The small opponent portraits used by the duel-selection interface are stored in
`DATA/WA_MRG.MRG`:

- region offset: `0x00F55000` (`16076800` decimal);
- slot count: `40`;
- record size/stride: `0x980` (`2432`) bytes;
- pixels: `48 x 48`, 8-bpp indexed (`0x900` bytes);
- palette: 64 little-endian PS1 ABGR1555 colors (`0x80` bytes), immediately
  following the pixel indexes.

This layout is explicitly described by the preserved Hack Suite source in
`GraphicUtils.java` under `Enemies - Selection`. It was reproduced locally by
`tools/extract_opponent_images.py`; all 40 records rendered with correct geometry
and colors in the Remastered, Naruto, and Naruto Shippuden Final files.

## Dataset-specific ID mapping

The 40 raw slots use the same semantic mapping in all three validated mods:

- raw slot 1 is the Free Duel deck-menu icon and is not an opponent;
- opponent IDs 1-39 use raw slots 2-40 (`--first-slot 2`);
- therefore the raw relation is `portrait_slot = opponent_id + 1`.

This offset was verified in the running catalog after the initial Naruto mapping
incorrectly treated slot 1 as Konohamaru: the deck icon appeared on Konohamaru,
and Konohamaru's real portrait appeared on Kakashi. Advancing every opponent by
one slot corrects that sequence. The slot-1 graphic is preserved separately as
`free_duel_deck.png` for future menu documentation, but the HTML does not use it.

The extractor preserves all raw slots with `--all`, while `--opponents` produces
39 website-ready files named by authoritative opponent ID. `--first-slot`
remains available for unvalidated mods, while its safe default is 2.

## Larger enemy graphics

The same Hack Suite source documents another `Enemies` region at decimal offset
`31092736`, with 65 records of `0x19000` bytes. Each record is a `128 x 768`
8-bpp sheet with four 256-color palettes. These are tall multi-frame graphics,
not the compact mugshots needed by the catalog tables. The `48 x 48` selection
portraits are therefore the appropriate first website asset.

## Public corroboration

- The Spriters Resource preserves the original game's mugshot sheet:
  https://www.spriters-resource.com/playstation/ygofm/asset/51205/
- A 2015 note describes a historical visualizer that consumed `SU.MRG`,
  `SLUS_014.11`, `WA_MRG.MRG`, and `MODEL.MRG`, while noting limitations around
  character-avatar export:
  https://lanee.blog.fc2.com/blog-entry-207.html
- Data Crystal's ROM map documents other known `WA_MRG.MRG` regions but does not
  currently include this portrait block:
  https://datacrystal.tcrf.net/wiki/Yu-Gi-Oh%21_Forbidden_Memories/ROM_map

Confidence is high for the byte layout and the three mappings because the result
was decoded and inspected rather than inferred from byte similarity alone.
