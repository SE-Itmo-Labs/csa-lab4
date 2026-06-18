import sys
import struct
from src.translator.lexer import tokenize
from src.translator.parser import Parser, print_ast
from src.translator.code_generator import Compiler
from src.isa.isa import disassemble

def main(source_file, target_file):
    with open(source_file, 'r', encoding='utf-8') as f: 
        source_code = f.read()
    
    # PARSING & AST
    ast = Parser(tokenize(source_code)).parse()
    print_ast(ast)
    
    # COMPILING
    compiler = Compiler()
    memory, debug_log, data_start = compiler.compile(ast)

    with open(target_file, "wb") as f:
        for word in memory: 
            f.write(struct.pack(">i", word))

    with open(target_file + ".log", "w", encoding="utf-8") as f:
        for addr, word in enumerate(memory):
            if word != 0:
                hex_code = f"{word & 0xFFFFFFFF:08X}"
                if addr < data_start:
                    f.write(f"{addr:04X} - {hex_code} - {disassemble(word)}\n")
                else:
                    char_repr = repr(chr(word)) if 32 <= word <= 126 else ""
                    f.write(f"{addr:04X} - {hex_code} - DATA: {word} {char_repr}\n")
    
    for line in debug_log: 
        print("  " + line)

    with open(target_file, "wb") as f:
        for word in memory: 
            f.write(struct.pack(">i", word))
            
    print(f"\nBinary saved to {target_file}")

if __name__ == '__main__':
    if len(sys.argv) != 3: 
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])