from __future__ import annotations

import argparse
import dataclasses
import pathlib
from typing import Iterable


RAW_SECTOR_SIZE = 2352
DATA_SECTOR_SIZE = 2048
MODE2_FORM1_DATA_OFFSET = 0x18
MODE2_FORM1_EDC_OFFSET = 0x818
MODE2_FORM1_ECC_P_OFFSET = 0x81C
MODE2_FORM1_ECC_Q_OFFSET = 0x8C8


def _build_edc_lut() -> tuple[int, ...]:
    table: list[int] = []
    for value in range(256):
        result = value
        for _ in range(8):
            result = (
                (result >> 1) ^ 0xD8018001 if result & 1 else result >> 1
            )
        table.append(result)
    return tuple(table)


def _build_ecc_luts() -> tuple[tuple[int, ...], tuple[int, ...]]:
    forward = [0] * 256
    backward = [0] * 256
    for value in range(256):
        result = (value << 1) ^ (0x11D if value & 0x80 else 0)
        forward[value] = result
        backward[value ^ result] = value
    return tuple(forward), tuple(backward)


EDC_LUT = _build_edc_lut()
ECC_FORWARD_LUT, ECC_BACKWARD_LUT = _build_ecc_luts()


def _compute_edc(data: bytes | bytearray) -> int:
    result = 0
    for value in data:
        result = (result >> 8) ^ EDC_LUT[(result ^ value) & 0xFF]
    return result


def _compute_ecc(
    source: bytes | bytearray,
    major_count: int,
    minor_count: int,
    major_multiplier: int,
    minor_increment: int,
) -> bytes:
    size = major_count * minor_count
    output = bytearray(major_count * 2)
    for major in range(major_count):
        index = (major >> 1) * major_multiplier + (major & 1)
        ecc_a = 0
        ecc_b = 0
        for _ in range(minor_count):
            value = source[index]
            index += minor_increment
            if index >= size:
                index -= size
            ecc_a ^= value
            ecc_b ^= value
            ecc_a = ECC_FORWARD_LUT[ecc_a]
        ecc_a = ECC_BACKWARD_LUT[ECC_FORWARD_LUT[ecc_a] ^ ecc_b]
        output[major] = ecc_a
        output[major + major_count] = ecc_a ^ ecc_b
    return bytes(output)


def _update_mode2_form1_checksums(sector: bytearray) -> None:
    if len(sector) != RAW_SECTOR_SIZE:
        raise ValueError(f"Setor raw incompleto: {len(sector)} bytes")
    if sector[15] != 2 or sector[18] & 0x20:
        raise ValueError("O setor nao e Mode 2/Form 1.")
    if sector[0x10:0x14] != sector[0x14:0x18]:
        raise ValueError("As duas copias do subheader XA sao diferentes.")

    edc = _compute_edc(sector[0x10:MODE2_FORM1_EDC_OFFSET])
    sector[MODE2_FORM1_EDC_OFFSET:MODE2_FORM1_ECC_P_OFFSET] = edc.to_bytes(
        4, "little"
    )

    header = bytes(sector[0x0C:0x10])
    sector[0x0C:0x10] = b"\x00" * 4
    sector[MODE2_FORM1_ECC_P_OFFSET:MODE2_FORM1_ECC_Q_OFFSET] = _compute_ecc(
        sector[0x0C:MODE2_FORM1_ECC_P_OFFSET], 86, 24, 2, 86
    )
    sector[MODE2_FORM1_ECC_Q_OFFSET:RAW_SECTOR_SIZE] = _compute_ecc(
        sector[0x0C:MODE2_FORM1_ECC_Q_OFFSET], 52, 43, 86, 88
    )
    sector[0x0C:0x10] = header


@dataclasses.dataclass(frozen=True)
class SectorLayout:
    sector_size: int
    data_offset: int


@dataclasses.dataclass(frozen=True)
class IsoEntry:
    path: str
    lba: int
    size: int
    is_dir: bool


def _detect_layout(image: pathlib.Path) -> SectorLayout:
    with image.open("rb") as f:
        sample = f.read(RAW_SECTOR_SIZE * 32)

    layouts = (
        SectorLayout(2048, 0),
        SectorLayout(2352, 24),
    )
    for layout in layouts:
        offset = 16 * layout.sector_size + layout.data_offset + 1
        if sample[offset : offset + 5] == b"CD001":
            return layout

    raise ValueError("Nao encontrei um volume ISO9660 valido nessa imagem.")


class PsxIso:
    def __init__(self, image: pathlib.Path, writable: bool = False):
        self.image = image
        self.layout = _detect_layout(image)
        self._file = image.open("r+b" if writable else "rb")
        self.root = self._read_root_record()

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> "PsxIso":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def read_sector(self, lba: int) -> bytes:
        offset = lba * self.layout.sector_size + self.layout.data_offset
        self._file.seek(offset)
        return self._file.read(DATA_SECTOR_SIZE)

    def read_file(self, lba: int, size: int) -> bytes:
        chunks: list[bytes] = []
        remaining = size
        while remaining > 0:
            sector = self.read_sector(lba)
            take = min(remaining, DATA_SECTOR_SIZE)
            chunks.append(sector[:take])
            remaining -= take
            lba += 1
        return b"".join(chunks)

    def iter_entries(self) -> Iterable[IsoEntry]:
        yield from self._iter_dir("", self.root.lba, self.root.size)

    def extract_all(self, output_dir: pathlib.Path) -> None:
        for entry in self.iter_entries():
            target = output_dir / entry.path
            if entry.is_dir:
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.read_file(entry.lba, entry.size))

    def find_file(self, path: str) -> IsoEntry:
        normalized = path.replace("\\", "/").strip("/").casefold()
        matches = [
            entry
            for entry in self.iter_entries()
            if not entry.is_dir and entry.path.casefold() == normalized
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Esperava exatamente um arquivo ISO chamado {path!r}; "
                f"encontrei {len(matches)}."
            )
        return matches[0]

    def replace_file(self, path: str, replacement: bytes) -> tuple[IsoEntry, int]:
        if not self._file.writable():
            raise ValueError("A imagem foi aberta somente para leitura.")
        entry = self.find_file(path)
        if len(replacement) != entry.size:
            raise ValueError(
                f"O substituto precisa ter o mesmo tamanho: "
                f"ISO={entry.size}, substituto={len(replacement)}"
            )

        remaining = entry.size
        source_offset = 0
        lba = entry.lba
        changed_sectors = 0
        rollback_chunks: list[tuple[int, bytes]] = []
        try:
            while remaining > 0:
                take = min(remaining, DATA_SECTOR_SIZE)
                physical_offset = lba * self.layout.sector_size
                new_data = replacement[source_offset : source_offset + take]
                if self.layout.sector_size == DATA_SECTOR_SIZE:
                    self._file.seek(physical_offset)
                    current_data = self._file.read(take)
                    if current_data != new_data:
                        rollback_chunks.append((physical_offset, current_data))
                        self._file.seek(physical_offset)
                        self._file.write(new_data)
                        changed_sectors += 1
                elif self.layout == SectorLayout(RAW_SECTOR_SIZE, MODE2_FORM1_DATA_OFFSET):
                    self._file.seek(physical_offset)
                    original_sector = self._file.read(RAW_SECTOR_SIZE)
                    sector = bytearray(original_sector)
                    current_data = sector[
                        MODE2_FORM1_DATA_OFFSET : MODE2_FORM1_DATA_OFFSET + take
                    ]
                    if current_data != new_data:
                        sector[
                            MODE2_FORM1_DATA_OFFSET : MODE2_FORM1_DATA_OFFSET + take
                        ] = new_data
                        _update_mode2_form1_checksums(sector)
                        rollback_chunks.append((physical_offset, original_sector))
                        self._file.seek(physical_offset)
                        self._file.write(sector)
                        changed_sectors += 1
                else:
                    raise ValueError(f"Layout gravavel nao suportado: {self.layout}")

                remaining -= take
                source_offset += take
                lba += 1

            self._file.flush()
        except Exception:
            for physical_offset, original_chunk in reversed(rollback_chunks):
                self._file.seek(physical_offset)
                self._file.write(original_chunk)
            self._file.flush()
            raise
        return entry, changed_sectors

    def _read_root_record(self) -> IsoEntry:
        pvd = self.read_sector(16)
        if pvd[1:6] != b"CD001":
            raise ValueError("Primary Volume Descriptor invalido.")
        return _parse_dir_record(pvd[156 : 156 + pvd[156]], "")

    def _iter_dir(self, parent: str, lba: int, size: int) -> Iterable[IsoEntry]:
        data = self.read_file(lba, size)
        pos = 0
        while pos < len(data):
            record_len = data[pos]
            if record_len == 0:
                pos = ((pos // DATA_SECTOR_SIZE) + 1) * DATA_SECTOR_SIZE
                continue

            record = data[pos : pos + record_len]
            entry = _parse_dir_record(record, parent)
            pos += record_len

            name = entry.path.rsplit("/", 1)[-1]
            if name in (".", ".."):
                continue

            yield entry
            if entry.is_dir:
                yield from self._iter_dir(entry.path, entry.lba, entry.size)


def _parse_dir_record(record: bytes, parent: str) -> IsoEntry:
    lba = int.from_bytes(record[2:6], "little")
    size = int.from_bytes(record[10:14], "little")
    flags = record[25]
    name_len = record[32]
    raw_name = record[33 : 33 + name_len]

    if raw_name == b"\x00":
        name = "."
    elif raw_name == b"\x01":
        name = ".."
    else:
        name = raw_name.decode("ascii", errors="replace").split(";")[0]

    path = name if not parent or name in (".", "..") else f"{parent}/{name}"
    return IsoEntry(path=path, lba=lba, size=size, is_dir=bool(flags & 0x02))


def _cmd_list(args: argparse.Namespace) -> None:
    with PsxIso(args.image) as iso:
        print(f"layout: sector={iso.layout.sector_size} data_offset={iso.layout.data_offset}")
        for entry in iso.iter_entries():
            kind = "DIR " if entry.is_dir else "FILE"
            print(f"{kind} {entry.lba:6d} {entry.size:10d} {entry.path}")


def _cmd_extract(args: argparse.Namespace) -> None:
    with PsxIso(args.image) as iso:
        iso.extract_all(args.output)
    print(f"Extraido em: {args.output}")


def _cmd_replace(args: argparse.Namespace) -> None:
    replacement = args.source.read_bytes()
    with PsxIso(args.image, writable=True) as iso:
        entry, changed_sectors = iso.replace_file(args.iso_path, replacement)

    with PsxIso(args.image) as iso:
        verified = iso.read_file(entry.lba, entry.size)
    if verified != replacement:
        raise RuntimeError("A verificacao apos a substituicao falhou.")
    print(
        f"Substituido e verificado: {entry.path} "
        f"({entry.size} bytes, LBA {entry.lba}, "
        f"setores alterados: {changed_sectors})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lista, extrai ou substitui arquivos ISO9660 em imagens de PS1."
    )
    parser.add_argument("image", type=pathlib.Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.set_defaults(func=_cmd_list)

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("output", type=pathlib.Path)
    extract_parser.set_defaults(func=_cmd_extract)

    replace_parser = subparsers.add_parser(
        "replace", help="substitui um arquivo existente sem mudar seu tamanho"
    )
    replace_parser.add_argument("iso_path", help="caminho interno, ex.: DATA/WA_MRG.MRG")
    replace_parser.add_argument("source", type=pathlib.Path)
    replace_parser.set_defaults(func=_cmd_replace)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
