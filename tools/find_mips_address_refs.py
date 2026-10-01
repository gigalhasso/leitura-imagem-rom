from __future__ import annotations

import argparse
import pathlib
import struct


def read_u32le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def decode_lui(instruction: int) -> tuple[int, int] | None:
    if instruction >> 26 != 0x0F:
        return None
    rt = (instruction >> 16) & 0x1F
    imm = instruction & 0xFFFF
    return rt, imm


def decode_imm_op(instruction: int) -> tuple[str, int, int, int] | None:
    opcode = instruction >> 26
    names = {
        0x08: "addi",
        0x09: "addiu",
        0x0C: "andi",
        0x0D: "ori",
    }
    if opcode not in names:
        return None
    rs = (instruction >> 21) & 0x1F
    rt = (instruction >> 16) & 0x1F
    imm = instruction & 0xFFFF
    return names[opcode], rs, rt, imm


def main() -> None:
    parser = argparse.ArgumentParser(description="Find simple MIPS LUI/immediate references to an address.")
    parser.add_argument("path", type=pathlib.Path)
    parser.add_argument("address", type=lambda value: int(value, 0))
    parser.add_argument("--window-instructions", type=int, default=8)
    args = parser.parse_args()

    data = args.path.read_bytes()
    hi = (args.address >> 16) & 0xFFFF
    lo = args.address & 0xFFFF

    for offset in range(0, len(data) - 4, 4):
        instruction = read_u32le(data, offset)
        lui = decode_lui(instruction)
        if not lui:
            continue
        rt, imm = lui
        if imm != hi:
            continue

        for lookahead in range(1, args.window_instructions + 1):
            next_offset = offset + lookahead * 4
            if next_offset + 4 > len(data):
                break
            next_instruction = read_u32le(data, next_offset)
            decoded = decode_imm_op(next_instruction)
            if not decoded:
                continue
            op, rs, next_rt, next_imm = decoded
            if rs == rt and next_imm == lo:
                print(
                    f"{args.path}\tlui_offset=0x{offset:08X}\t"
                    f"{op}_offset=0x{next_offset:08X}\treg=${rt}\taddress=0x{args.address:08X}"
                )


if __name__ == "__main__":
    main()
