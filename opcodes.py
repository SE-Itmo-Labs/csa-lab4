from enum import IntEnum

class Opcode(IntEnum):
    NOP = 0x00
    
    # Работа со стеком
    PUSH = 0x01
    LOAD = 0x02
    STORE = 0x03
    DUP = 0x04       # Дублировать TOS (Top of Stack)
    DROP = 0x05      # Удалить TOS
    TOR = 0x21       # TOS -> R (Return Stack)
    NEXT = 0x22      # if R != 0: R--, JMP arg. else: POP RS
    
    # Integer
    ADD = 0x06
    SUB = 0x07
    MUL = 0x08
    DIV = 0x09
    MOD = 0x0A
    
    # Float
    FADD = 0x0B
    FSUB = 0x0C
    FMUL = 0x0D
    FDIV = 0x0E
    
    # Условные переходы
    CMP = 0x0F       #  (==)
    NEQ = 0x10       #  (!=)
    GT = 0x11        #  (>)
    LT = 0x12        #  (<)
    
    # Переходы
    JMP = 0x13
    JZ = 0x14        # JMP if TOS == 0
    CALL = 0x15
    RET = 0x16
    
    # Прерывания
    HALT = 0x17
    EI = 0x18
    IRET = 0x19
    DI = 0x1A

    # Битовые операции
    AND = 0x1B
    OR = 0x1C
    XOR = 0x1D
    NOT = 0x1E
    SHL = 0x1F
    SHR = 0x20