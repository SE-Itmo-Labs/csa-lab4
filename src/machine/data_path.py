from constants import MEMORY_SIZE, MMIO_INPUT, MMIO_OUTPUT_CHAR, MMIO_OUTPUT_NUM, MMIO_OUTPUT_FLOAT
from constants import DATA_STACK_SIZE, RETURN_STACK_SIZE
import struct

def bits_to_float(i: int) -> float:
    return struct.unpack('>f', struct.pack('>i', i))[0]

class DataPath:
    def __init__(self, memory_init: list[int], io_schedule: list[tuple[int, str]]):
        self.memory = memory_init + [0] * (MEMORY_SIZE - len(memory_init))
        
        self.data_stack = [0] * DATA_STACK_SIZE
        self.dsp = 0
        self.return_stack = [0] * RETURN_STACK_SIZE
        self.rsp = 0

        self.r = 0

        self.ar = 0
        self.dr = 0
        
        self.schedule = io_schedule
        self.input_register = 0
        self.out_buffer = ""
        
        self.temp_long_low = 0
        
        self.irq_io = False
        self.irq_so_data = False
        self.irq_so_ret = False

    @property
    def t(self) -> int:
        return self.data_stack[self.dsp - 1] if self.dsp > 0 else 0

    @property
    def s(self) -> int:
        return self.data_stack[self.dsp - 2] if self.dsp > 1 else 0

    def push(self, val: int):
        if self.dsp >= DATA_STACK_SIZE:
            return
        
        self.data_stack[self.dsp] = val
        self.dsp += 1

        if self.dsp == DATA_STACK_SIZE - 1:
            self.irq_so_data = True

    def pop(self) -> int:
        if self.dsp <= 0: 
            return 0
        self.dsp -= 1
        return self.data_stack[self.dsp]
    
    def clear_data_stack(self):
        self.dsp = 0
        
    def clear_return_stack(self):
        self.rsp = 0
        self.r = 0

    def push_rs(self, val: int, is_hw: bool = False):

        if self.rsp >= RETURN_STACK_SIZE:
            if not is_hw:
                raise RuntimeError("FATAL ERROR: DOUBLE FAULT (RS OVERFLOW)")
            return 
        
        self.return_stack[self.rsp] = self.r
        self.rsp += 1

        self.r = val
        
        if self.rsp == RETURN_STACK_SIZE - 1:
            self.irq_so_ret = True

    def pop_rs(self) -> int:

        val = self.r

        if self.rsp <= 0:
            self.rsp = 0
            self.r = 0
        else:
            self.rsp -= 1
            self.r = self.return_stack[self.rsp]

        return val

    def read_mem(self, addr: int) -> int:
        if addr == MMIO_INPUT:
            val = self.input_register
            self.irq_io = False 
            return val
        return self.memory[addr]

    def write_mem(self, addr: int, val: int):
        if addr == MMIO_OUTPUT_CHAR:
            self.out_buffer += chr(val % 256)
        elif addr == MMIO_OUTPUT_NUM:
            self.out_buffer += str(val)
        elif addr == MMIO_OUTPUT_FLOAT:
            self.out_buffer += f"{bits_to_float(val):.3f}"
        else:
            self.memory[addr] = val

    def process_io_background(self, current_tick: int):
        while self.schedule and current_tick >= self.schedule[0][0]:
            _, val = self.schedule.pop(0)

            if isinstance(val, int):
                self.input_register = val
            elif isinstance(val, str):
                if val in ('\\0', '\0'):
                    self.input_register = -999
                else:
                    try:
                        self.input_register = int(val)
                    except ValueError:
                        self.input_register = ord(val[0])

            self.irq_io = True