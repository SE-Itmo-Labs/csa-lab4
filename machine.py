import sys
import ast
import logging
from constants import CODE_START
from src.machine.control_unit import ControlUnit
from src.machine.data_path import DataPath
from src.isa.isa import read_binary

def main(code_file: str, schedule_file: str):
    # Настраиваем логирование
    
    memory = read_binary(code_file)
    
    schedule = []
    try:
        with open(schedule_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                schedule = ast.literal_eval(content)
    except FileNotFoundError:
        logging.warning("Schedule file not found, using empty input.")

    dp = DataPath(memory, schedule)
    cpu = ControlUnit(dp)
    
    # Стартуем с 0 адреса (или с того, что определит твой компилятор в будущем)
    cpu.pc = CODE_START # start at 1st JUMP
    cpu.run()

    print(dp.out_buffer, end="")

if __name__ == "__main__":

    logging.basicConfig(
        filename="simulation.log",
        filemode="w",
        level=logging.DEBUG,
        format="%(message)s",
        encoding="utf-8",
        force=False
    )

    if len(sys.argv) < 2:
        print("Usage: python machine.py <code.bin> [<schedule.txt>]")
        sys.exit(1)

    code_file = sys.argv[1]
    schedule_file = sys.argv[2] if len(sys.argv) > 2 else ''

    main(code_file, schedule_file)