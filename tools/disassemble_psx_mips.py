from __future__ import annotations

import argparse
import pathlib
import struct

from capstone import CS_ARCH_MIPS, CS_MODE_LITTLE_ENDIAN, CS_MODE_MIPS32, Cs


PSX_EXE_HEADER_SIZE = 0x800


def read_load_address(data: bytes) -> int:
    if not data.startswith(b"PS-X EXE"):
        raise ValueError("input is not a PS-X EXE")
    return struct.unpack_from("<I", data, 0x18)[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Disassemble a window of a PS-X EXE.")
    parser.add_argument("path", type=pathlib.Path)
    parser.add_argument("offset", type=lambda value: int(value, 0))
    parser.add_argument("--before", type=lambda value: int(value, 0), default=0x40)
    parser.add_argument("--after", type=lambda value: int(value, 0), default=0x100)
    args = parser.parse_args()

    data = args.path.read_bytes()
    load_address = read_load_address(data)
    start = max(PSX_EXE_HEADER_SIZE, (args.offset - args.before) & ~3)
    end = min(len(data), (args.offset + args.after + 3) & ~3)
    virtual_address = load_address + start - PSX_EXE_HEADER_SIZE

    disassembler = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
    for instruction in disassembler.disasm(data[start:end], virtual_address):
        marker = ">" if start + instruction.address - virtual_address == args.offset else " "
        file_offset = start + instruction.address - virtual_address
        print(
            f"{marker} 0x{file_offset:08X}  0x{instruction.address:08X}  "
            f"{instruction.mnemonic:<8} {instruction.op_str}"
        )


if __name__ == "__main__":
    main()
