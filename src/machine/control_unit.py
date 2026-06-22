import logging
import struct
from src.isa.opcodes import Opcode
from src.isa.isa import decode_instruction
from constants import CODE_START, MMIO_OUTPUT_NUM, VECTOR_IO, VECTOR_SO_DATA, VECTOR_SO_RET

def to_signed64(val):
    val &= 0xFFFFFFFFFFFFFFFF
    return val - 0x10000000000000000 if val & 0x8000000000000000 else val

def float_to_bits(f: float) -> int:
    return struct.unpack('>i', struct.pack('>f', f))[0]

def bits_to_float(i: int) -> float:
    return struct.unpack('>f', struct.pack('>i', i))[0]

def to_signed32(val):
    val &= 0xFFFFFFFF
    return val - 0x100000000 if val & 0x80000000 else val

# IEEE-754

def unpack_f32(bits):
    sign = (bits >> 31) & 1
    exp = (bits >> 23) & 0xFF
    frac = bits & 0x7FFFFF
    mant = frac | 0x800000 if exp > 0 else frac
    return sign, exp, mant

def pack_f32(sign, exp, mant):
    if exp <= 0: return 0
    if exp >= 255: return (sign << 31) | (0xFF << 23)
    frac = mant & 0x7FFFFF
    return (sign << 31) | (exp << 23) | frac

class ControlUnit:
    def __init__(self, data_path):

        self.dp = data_path
        self.pc = CODE_START
        self.tick_counter = 0

        self.ie = False

        self.eam = False 

        self.halted = False

        self.instr_gen = None
        self.current_pc = 0
        self.current_op = None
        self.current_arg = 0

    def get_eam_operands(self):
        b_high, b_low = self.dp.pop(), self.dp.pop()
        a_high, a_low = self.dp.pop(), self.dp.pop()
        b = ((b_high & 0xFFFFFFFF) << 32) | (b_low & 0xFFFFFFFF)
        a = ((a_high & 0xFFFFFFFF) << 32) | (a_low & 0xFFFFFFFF)
        return to_signed64(a), to_signed64(b)

    def push_eam_result(self, res):
        res_uint = res & 0xFFFFFFFFFFFFFFFF
        self.dp.push(res_uint & 0xFFFFFFFF)
        self.dp.push((res_uint >> 32) & 0xFFFFFFFF)

    def log_tick(self, op_name, arg, phase=""):
        arg_str = ""
        if op_name in ("PUSH", "JMP", "JZ", "CALL", "NEXT", "SEAM", "CEAM"):
            arg_str = f" {arg}"
            
        eam_flag = " [EAM]" if self.eam else ""
        phase_str = f" | {phase}" if phase else ""
        logging.debug(f"{self.tick_counter:04d} PC {self.current_pc:04X} | {op_name}{arg_str}{eam_flag} | RSP {self.dp.rsp} | DSP {self.dp.dsp} | T {self.dp.t} | S {self.dp.s} | R {self.dp.r} | AR {self.dp.ar} | DR {self.dp.dr}{phase_str}")
    
    def tick(self):

        if self.halted:
            return

        self.tick_counter += 1
        self.dp.process_io_background(self.tick_counter)

        if self.instr_gen is not None:
            try:
                next(self.instr_gen)
                return
            except StopIteration:
                self.instr_gen = None
        
        # INFETCH

        # DATA STACK OVERFLOW, RET STACK OVERFLOW
        if self.dp.irq_so_ret:
            self.dp.irq_so_ret = False
            self.ie = False
            self.dp.push_rs(self.pc, is_hw = True)
            self.pc = VECTOR_SO_RET
            logging.warning(f"Tick: {self.tick_counter:04d} | HARDWARE FAULT: Return Stack Overflow!")
            return
        
        if self.dp.irq_so_data:
            self.dp.irq_so_data = False
            self.ie = False
            self.dp.push_rs(self.pc, is_hw = True)
            self.pc = VECTOR_SO_DATA
            logging.warning(f"Tick: {self.tick_counter:04d} | HARDWARE FAULT: Data Stack Overflow!")
            return
        
        # IO
        if self.dp.irq_io and self.ie:
            self.dp.irq_io = False
            self.ie = False
            self.dp.push_rs(self.pc, is_hw = True)
            self.pc = VECTOR_IO
            logging.debug(f"Tick: {self.tick_counter:04d} | IO INTERRUPT Triggered! Jumping to {VECTOR_IO:04X}")
            return

        word = self.dp.read_mem(self.pc)
        self.current_op, self.current_arg = decode_instruction(word)
        self.current_pc = self.pc
        self.pc += 1
        
        self.log_tick(self.current_op.name, self.current_arg, "FETCH")
        
        self.instr_gen = self.execute_instruction(self.current_op, self.current_arg)

    def execute_instruction(self, op: Opcode, arg: int):
        op_name = op.name

        if op == Opcode.NOP:
            self.log_tick(op_name, arg, "NOP command")
            yield
        
        # yield - последовательная схема / конечные автоматы
        elif op == Opcode.HALT: 
            self.halted = True
            self.log_tick(op_name, arg, "HALT Latch")
            yield

        elif op == Opcode.PUSH: 
            self.dp.push(arg)
            self.log_tick(op_name, arg, "T <- ARG")
            yield
            
        elif op == Opcode.SEAM:
            self.eam = True
            self.log_tick(op_name, arg, "EAM Enabled")
            yield
            
        elif op == Opcode.CEAM:
            self.eam = False
            self.log_tick(op_name, arg, "EAM Disabled")
            yield

        elif op == Opcode.LOAD: 
            self.dp.ar = self.dp.pop()
            self.log_tick(op_name, arg, "AR <- T")
            yield 
            self.dp.dr = self.dp.read_mem(self.dp.ar)
            self.log_tick(op_name, arg, "DR <- MEM[AR]")
            yield
            if self.eam:
                self.dp.push(self.dp.dr)
                self.dp.dr = self.dp.read_mem(self.dp.ar + 1)
                self.log_tick(op_name, arg, "DR <- MEM[AR+1] (EAM)")
                yield
                self.dp.push(self.dp.dr)
                self.log_tick(op_name, arg, "T <- DR_HIGH (EAM)")
                yield
            else:
                self.dp.push(self.dp.dr)
                self.log_tick(op_name, arg, "T <- DR")
                yield

        elif op == Opcode.STORE:
            if self.eam:
                self.dp.ar = self.dp.pop()
                dr_high = self.dp.pop()
                dr_low = self.dp.pop()
                self.log_tick(op_name, arg, "AR <- Addr, DR <- Ext Data")
                yield
                if self.dp.ar == MMIO_OUTPUT_NUM:

                    combined = ((dr_high & 0xFFFFFFFF) << 32) | (dr_low & 0xFFFFFFFF)
                    self.dp.write_mem(self.dp.ar, to_signed64(combined))
                    self.log_tick(op_name, arg, "MMIO[AR] <- DR_64 (EAM)")
                    yield
                else:
                    self.dp.write_mem(self.dp.ar, dr_low)
                    self.log_tick(op_name, arg, "MEM[AR] <- DR_LOW (EAM)")
                    yield
                    self.dp.write_mem(self.dp.ar + 1, dr_high)
                    self.log_tick(op_name, arg, "MEM[AR+1] <- DR_HIGH (EAM)")
                    yield
            else:
                self.dp.ar = self.dp.pop()
                self.dp.dr = self.dp.pop()
                self.log_tick(op_name, arg, "AR <- T, DR <- S")
                yield
                self.dp.write_mem(self.dp.ar, self.dp.dr)
                self.log_tick(op_name, arg, "MEM[AR] <- DR")
                yield

        elif op == Opcode.DUP:
            self.dp.push(self.dp.t)
            self.log_tick(op_name, arg, "T Duplicated")
            yield
            
        elif op == Opcode.DROP:
            self.dp.pop()
            self.log_tick(op_name, arg, "Dropped T")
            yield

        elif op == Opcode.SEXT:
            low = self.dp.t                    
            high = 0xFFFFFFFF if (low & 0x80000000) else 0
            self.dp.push(to_signed32(high))
            self.log_tick(op_name, arg, "SEXT 32->64")
            yield
        
        # INT Math
        elif op == Opcode.ADD: 
            if self.eam:
                a, b = self.get_eam_operands()
                self.push_eam_result(a + b)
                self.log_tick(op_name, arg, "EAM ALU ADD")
                yield
            else:
                res = (self.dp.s + self.dp.t) & 0xFFFFFFFF
                self.dp.pop(); self.dp.pop()
                self.dp.push(to_signed32(res))
                self.log_tick(op_name, arg, "ALU ADD")
                yield

        elif op == Opcode.SUB:
            if self.eam:
                a, b = self.get_eam_operands()
                self.push_eam_result(a - b)
                self.log_tick(op_name, arg, "EAM ALU SUB")
                yield
            else:
                # S + ~T + 1
                t_inv = (~self.dp.t) & 0xFFFFFFFF
                res = (self.dp.s + t_inv + 1) & 0xFFFFFFFF
                self.dp.pop(); self.dp.pop()
                self.dp.push(to_signed32(res))
                self.log_tick(op_name, arg, "ALU SUB")
                yield

        # Binary logic
        elif op == Opcode.AND:
            res = (self.dp.s & self.dp.t) & 0xFFFFFFFF
            self.dp.pop(); self.dp.pop()
            self.dp.push(to_signed32(res))
            self.log_tick(op_name, arg, "ALU AND")
            yield

        elif op == Opcode.OR:
            res = (self.dp.s | self.dp.t) & 0xFFFFFFFF
            self.dp.pop(); self.dp.pop()
            self.dp.push(to_signed32(res))
            self.log_tick(op_name, arg, "ALU OR")
            yield

        elif op == Opcode.XOR:
            res = (self.dp.s ^ self.dp.t) & 0xFFFFFFFF
            self.dp.pop(); self.dp.pop()
            self.dp.push(to_signed32(res))
            self.log_tick(op_name, arg, "ALU XOR")
            yield

        elif op == Opcode.NOT:
            res = (~self.dp.t) & 0xFFFFFFFF
            self.dp.pop()
            self.dp.push(to_signed32(res))
            self.log_tick(op_name, arg, "ALU NOT")
            yield

        elif op == Opcode.SHL:
            res = (self.dp.s << (self.dp.t & 0x1F)) & 0xFFFFFFFF
            self.dp.pop(); self.dp.pop()
            self.dp.push(to_signed32(res))
            self.log_tick(op_name, arg, "ALU SHL")
            yield

        elif op == Opcode.SHR:
            res = (self.dp.s >> (self.dp.t & 0x1F)) & 0xFFFFFFFF
            self.dp.pop(); self.dp.pop()
            self.dp.push(to_signed32(res))
            self.log_tick(op_name, arg, "ALU SHR")
            yield

        elif op in (Opcode.CMP, Opcode.NEQ, Opcode.GT, Opcode.LT):
            # flags
            t_inv = (~self.dp.t) & 0xFFFFFFFF
            res = (self.dp.s + t_inv + 1) & 0xFFFFFFFF
            
            Z = 1 if res == 0 else 0
            N = (res >> 31) & 1

            S_sign = (self.dp.s >> 31) & 1
            T_sign = (self.dp.t >> 31) & 1
            
            V = 1 if (S_sign != T_sign) and (S_sign != N) else 0

            self.dp.pop(); self.dp.pop()
            
            if op == Opcode.CMP: self.dp.push(1 if Z else 0)
            elif op == Opcode.NEQ: self.dp.push(0 if Z else 1)
            elif op == Opcode.GT: self.dp.push(1 if (Z == 0 and N == V) else 0)
            elif op == Opcode.LT: self.dp.push(1 if (N != V) else 0)
            
            self.log_tick(op_name, arg, f"ALU Subtractor (Z={Z} N={N} V={V})")
            yield

        elif op == Opcode.MUL: 
            if self.eam:
                a, b = self.get_eam_operands()
                self.push_eam_result(a * b)
                self.log_tick(op_name, arg, "EAM ALU MUL")
                yield
            else:
                s_sign = 1 if self.dp.s < 0 else 0
                t_sign = 1 if self.dp.t < 0 else 0
                res_sign = s_sign ^ t_sign
                
                multiplicand = abs(self.dp.s) & 0xFFFFFFFF
                multiplier = abs(self.dp.t) & 0xFFFFFFFF
                
                self.dp.ar = multiplier
                self.dp.pop(); self.dp.pop()
                self.dp.push(multiplicand) # S
                self.dp.push(0) # T 

                self.log_tick(op_name, arg, "MUL Setup")
                yield

                for i in range(32):

                    self.log_tick(op_name, arg, f"MUL Step {i+1}/32")
                    yield

                    # T <- T + (if A[0] then S else 0)
                    if self.dp.ar & 1:
                        self.dp.data_stack[self.dp.dsp - 1] = (self.dp.t + self.dp.s) & 0xFFFFFFFF
                        
                    # A <- A >> 1; A[31] <- T[0]; T <- T >> 1
                    t_lsb = self.dp.t & 1
                    self.dp.ar = (self.dp.ar >> 1) | (t_lsb << 31)
                    self.dp.data_stack[self.dp.dsp - 1] = self.dp.t >> 1
                    
                res = self.dp.ar
                if res_sign: res = -res
                self.dp.pop(); self.dp.pop()
                self.dp.push(to_signed32(res))
                self.log_tick(op_name, arg, "MUL Result")
                yield
            
        elif op in (Opcode.DIV, Opcode.MOD):
            s_sign = 1 if self.dp.s < 0 else 0
            t_sign = 1 if self.dp.t < 0 else 0
            res_sign = s_sign ^ t_sign
            mod_sign = s_sign
            
            dividend = abs(self.dp.s) & 0xFFFFFFFF
            divisor = abs(self.dp.t) & 0xFFFFFFFF
            
            self.dp.ar = dividend
            self.dp.dr = divisor
            self.dp.pop(); self.dp.pop()
            self.dp.push(0) # S (Partial remainder)
            self.dp.push(0) # T (Partial quotient)

            self.log_tick(op_name, arg, f"{op_name} Setup")
            yield
            
            for i in range(32):
                self.log_tick(op_name, arg, f"DIV Step {i+1}/32")
                yield

                # S <- S << 1; if A[31] then S[0] <- 1
                s_val = (self.dp.s << 1) & 0xFFFFFFFF
                if (self.dp.ar >> 31) & 1: s_val |= 1
                self.dp.data_stack[self.dp.dsp - 2] = s_val

                # A <- A << 1
                self.dp.ar = (self.dp.ar << 1) & 0xFFFFFFFF

                # T <- T << 1
                t_val = (self.dp.t << 1) & 0xFFFFFFFF

                # if S >= DR then S <- S - DR; T[0] <- 1
                if self.dp.s >= self.dp.dr and self.dp.dr != 0:
                    self.dp.data_stack[self.dp.dsp - 2] = (self.dp.s - self.dp.dr) & 0xFFFFFFFF
                    t_val |= 1

                self.dp.data_stack[self.dp.dsp - 1] = t_val

            quotient = self.dp.t
            remainder = self.dp.s
            if res_sign: quotient = -quotient
            if mod_sign: remainder = -remainder
            
            self.dp.pop(); self.dp.pop()
            if op == Opcode.DIV: self.dp.push(to_signed32(quotient))
            else: self.dp.push(to_signed32(remainder))
            self.log_tick(op_name, arg, f"{op_name} Result")
            yield

        # NEXT & DATA MOVEMENT BETWEEN T AND R

        elif op == Opcode.TOR:
            val = self.dp.pop()
            self.dp.push_rs(val)
            self.log_tick(op_name, arg, "R <- T")
            yield

        elif op == Opcode.NEXT:

            self.dp.r -= 1

            if self.dp.r > 0:
                self.pc = arg
                self.log_tick(op_name, arg, f"R = {self.dp.r} > 0, JUMP")
            else:
                self.dp.pop_rs()  # Докрутили до 0, возвращаем R из памяти RS
                self.log_tick(op_name, arg, "R == 0, Loop End (POP RS)")
            yield

        # FLOAT Math (IEEE-754 mantissa/exponent logic)
        elif op == Opcode.FMUL:
            self.log_tick(op_name, arg, "FPU: Сравнение порядков")
            yield
            sa, ea, ma = unpack_f32(self.dp.s)
            sb, eb, mb = unpack_f32(self.dp.t)
            sc = sa ^ sb
            if ea == 0 or eb == 0:
                res = 0
            else:
                ec = ea + eb - 127
                self.log_tick(op_name, arg, "FPU: Умножение мантисс")
                yield
                
                mc = 0
                for i in range(24):
                    self.log_tick(op_name, arg, f"FPU: FMUL Step {i+1}/24")
                    if (mb >> i) & 1:
                        mc += ma << i
                    yield
                
                self.log_tick(op_name, arg, "FPU: Нормализация и Округление")
                yield
                if mc & (1 << 47):
                    mc >>= 24
                    ec += 1
                else: 
                    mc >>= 23
                res = pack_f32(sc, ec, mc)
                
            self.dp.pop()
            self.dp.pop()
            self.dp.push(res)
            self.log_tick(op_name, arg, "FPU Result Latch")
            yield

        elif op == Opcode.FDIV:
            self.log_tick(op_name, arg, "FPU: Вычитание порядков")
            yield
            sa, ea, ma = unpack_f32(self.dp.s)
            sb, eb, mb = unpack_f32(self.dp.t)
            sc = sa ^ sb
            if eb == 0: 
                res = (sc << 31) | (0xFF << 23)
            elif ea == 0:
                res = 0
            else:
                ec = ea - eb + 127
                self.log_tick(op_name, arg, "FPU: Деление мантисс")
                yield
                
                dividend = ma << 24
                divisor = mb
                mc = 0
                for i in range(25, -1, -1):
                    self.log_tick(op_name, arg, f"FPU: FDIV Step {26 - i}/26")
                    if dividend >= (divisor << i):
                        dividend -= divisor << i
                        mc |= (1 << i)
                    yield
                
                self.log_tick(op_name, arg, "FPU: Нормализация")
                yield
                if (mc & (1 << 24)) == 0:
                    mc <<= 1
                    ec -= 1
                mc >>= 1
                res = pack_f32(sc, ec, mc)
                
            self.dp.pop()
            self.dp.pop()
            self.dp.push(res)
            self.log_tick(op_name, arg, "FPU Result Latch")
            yield

        elif op in (Opcode.FADD, Opcode.FSUB):
            for phase in ["Распаковка", "Выравнивание порядков", "Сложение/Вычитание мантисс", "Нормализация"]:
                self.log_tick(op_name, arg, f"FPU: {phase}")
                yield
            fb, fa = bits_to_float(self.dp.s), bits_to_float(self.dp.t)
            res = fb + fa if op == Opcode.FADD else fb - fa
            self.dp.pop(); self.dp.pop()
            self.dp.push(float_to_bits(res))
            self.log_tick(op_name, arg, "FPU Result Latch")
            yield
    

        elif op == Opcode.JMP: 
            self.pc = arg
            self.log_tick(op_name, arg, "JMP")
            yield

        elif op == Opcode.JZ:

            if self.dp.pop() == 0: 
                self.pc = arg

            self.log_tick(op_name, arg, "JZ")
            yield

        elif op == Opcode.CALL:
            self.dp.push_rs(self.pc)
            self.pc = arg

            self.log_tick(op_name, arg, "CALL")
            yield

        elif op == Opcode.RET: 
            self.pc = self.dp.pop_rs()

            self.log_tick(op_name, arg, "RET")
            yield

        elif op == Opcode.EI: 
            self.ie = True

            self.log_tick(op_name, arg, "INT Enable")
            yield

        elif op == Opcode.DI: 
            self.ie = False

            self.log_tick(op_name, arg, "INT Disable")
            yield

        elif op == Opcode.IRET:
            if self.dp.rsp == 0:
                logging.error(f"Tick: {self.tick_counter:04d} | IRET on empty Return Stack! Halting to prevent loop.")
                self.halted = True
                self.log_tick(op_name, arg, "IRET FAULT")
                yield
                return
            self.pc = self.dp.pop_rs()
            self.ie = True
            self.log_tick(op_name, arg, "IRET")
            yield


    def run(self):
        
        try:
            while not self.halted and self.tick_counter < 100000:
                self.tick()
        except Exception as e:
            logging.error(f"Execution Fault at PC {self.pc-1:04X}: {e}")

        logging.info(f"Total Ticks: {self.tick_counter}")
        logging.info(f"Output:\n{self.dp.out_buffer}")