from __future__ import annotations

import argparse
import pathlib
import re


ASCII_RE = re.compile(rb"[\x20-\x7e]{4,}")


def iter_ascii_strings(data: bytes):
    for match in ASCII_RE.finditer(data):
        yield match.start(), match.group().decode("ascii", errors="replace")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrai strings ASCII simples de arquivos binarios.")
    parser.add_argument("paths", nargs="+", type=pathlib.Path)
    parser.add_argument("--contains", default="", help="Filtra strings por trecho, sem diferenciar maiusculas.")
    args = parser.parse_args()

    needle = args.contains.lower()
    for path in args.paths:
        if path.is_dir():
            files = [p for p in path.rglob("*") if p.is_file()]
        else:
            files = [path]

        for file_path in files:
            data = file_path.read_bytes()
            for offset, text in iter_ascii_strings(data):
                if needle and needle not in text.lower():
                    continue
                print(f"{file_path}\t0x{offset:08X}\t{text}")


if __name__ == "__main__":
    main()
