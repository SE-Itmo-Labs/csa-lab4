import struct
from .opcodes import Opcode

def encode_instruction(opcode: Opcode, operand: int = 0) -> int:
    """Упаковывает код операции и операнд в 32-битное слово."""
    op = int(opcode) & 0xFF
    arg = int(operand) & 0xFFFFFF
    return (op << 24) | arg

def decode_instruction(word: int) -> tuple[Opcode, int]:
    """Распаковывает 32-битное слово."""
    op = (word >> 24) & 0xFF
    arg = word & 0xFFFFFF
    # Знаковое расширение для 24-битного аргумента (если нужно будет для JMP)
    if arg & 0x800000:
        arg -= 0x1000000
    
    try:
        return Opcode(op), arg
    except ValueError:
        return Opcode.NOP, 0

def read_binary(filepath: str) -> list[int]:
    """Читает бинарный файл в список 32-битных чисел (память)."""
    memory = []
    with open(filepath, "rb") as f:
        while chunk := f.read(4):
            if len(chunk) == 4:
                memory.append(struct.unpack(">i", chunk)[0])
    return memory

def disassemble(word: int) -> str:
    opcode, arg = decode_instruction(word)

    if opcode.name in ("PUSH", "JMP", "JZ", "CALL", "NEXT", "SEAM", "CEAM"):
        return f"{opcode.name} {arg}"
    
    return opcode.name

def write_code(filepath: str, memory: list[int]):
    with open(filepath, "wb") as f:
        for word in memory:
            import struct
            f.write(struct.pack(">i", word))