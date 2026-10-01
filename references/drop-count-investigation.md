# Multi-card drop count

Investigated on 2026-07-18 by comparing these extracted mods:

- `extracted`: current Remastered workspace copy
- `extracted_naruto`: Naruto Drop x15
- `extracted_naruto_shippuden_final`: Naruto Final Drop x5

The public `YGOFMDROPMORECARDSBYGHOST.exe` tool was downloaded from the
[installation guide](https://hippochan.nl/multi-card-drop/) and inspected
statically. It was not executed. SHA-256:
`5b02faa1b45ee2397b3bf2f69af61f2e75462c7807919b5d6cfe5a68ee272ae3`.

## Encoding

The number of awarded cards is an unsigned byte, constrained by the tool to
`1..15`. It is not a 16-bit value. The injected code needs both `N` and
`N + 1` loop limits.

The tool reads the current value as `WA_MRG.MRG[0x00BC1C78] - 1`.

### `N + 1` byte offsets in `DATA/WA_MRG.MRG`

```text
0x00BC17E4
0x00BC1C78  0x00C37478  0x00CACC78  0x00D22478
0x00D97C78  0x00E0D478  0x00E82C78
0x00BC1D74  0x00C37574  0x00CACD74  0x00D22574
0x00D97D74  0x00E0D574  0x00E82D74
```

### `N` byte offsets in `DATA/WA_MRG.MRG`

```text
0x00BC1DEC  0x00C375EC  0x00CACDEC  0x00D225EC
0x00D97DEC  0x00E0D5EC  0x00E82DEC
```

The seven repeated groups are separated by a stride of `0x75800` bytes.

## `SLUS` role

The count itself is not stored as a varying `1/5/15` value in the compared
`SLUS` files. The Ghost tool installs hooks at file offsets `0x12034`,
`0x1246C`, `0x12710`, and `0x285FC`, plus its MIPS routine at `0x19B400`.
The count-dependent bytes are in `WA_MRG.MRG`.

## Local validation

Every listed count offset agrees within each compatible mod:

| Workspace copy | `N + 1` | `N` | Effective count |
| --- | ---: | ---: | ---: |
| `extracted` | 16 | 15 | 15 |
| `extracted_naruto` | 16 | 15 | 15 |
| `extracted_naruto_shippuden_final` | 6 | 5 | 5 |

Therefore the current `extracted` copy is already Drop x15, not Drop x1.
The `extracted/reference_mod15` files do not contain this Ghost-tool layout
at the same offsets and must not be edited using this offset list without a
separate compatibility check.

## External evidence

- [Multi-card-drop installation guide](https://hippochan.nl/multi-card-drop/):
  confirms the Ghost tool takes both `SLUS_014.11` and `WA_MRG.MRG` and accepts
  a count from 1 through 15.
- [Data Crystal ROM map](https://datacrystal.tcrf.net/wiki/Yu-Gi-Oh%21_Forbidden_Memories/ROM_map):
  documents the original duel-end and card-drop routines used to identify the
  patched hook near runtime address `0x80021C5C`.

## Editor

`tools/edit_drop_count.py` inspects the current count by default:

```powershell
python tools/edit_drop_count.py extracted\DATA\WA_MRG.MRG
```

Supplying a count without `--write` performs a dry run:

```powershell
python tools/edit_drop_count.py extracted\DATA\WA_MRG.MRG 5
```

Writing requires `--write`. The editor validates all signatures and count
bytes, creates or preserves `WA_MRG.MRG.drop-count.bak`, writes atomically,
and verifies the saved file:

```powershell
python tools/edit_drop_count.py extracted\DATA\WA_MRG.MRG 5 --write
```
