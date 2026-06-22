import struct
from src.isa.opcodes import Opcode
from src.isa.isa import encode_instruction, decode_instruction
from constants import CODE_START, DATA_START, MMIO_INPUT, MMIO_OUTPUT_NUM, MMIO_OUTPUT_FLOAT, MMIO_OUTPUT_CHAR, VECTOR_IO, VECTOR_SO_DATA, VECTOR_SO_RET
from src.machine.control_unit import to_signed32
from .ast import *

def float_to_bits(f: float) -> int:
    return struct.unpack('>i', struct.pack('>f', f))[0]

class Compiler:
    def __init__(self):
        self.memory = [encode_instruction(Opcode.NOP)] * 2048
        self.machine_code = []
        self.pc = CODE_START
                               
        self.data_memory = []  
        self.next_data = 0      
        self.data_refs = [] 

        self.symbols = {}
        self.functions = {}
        self.function_types = {}
        self.unresolved_calls = []

    def emit(self, op: Opcode, arg: int = 0, is_data=False):
        addr = self.pc
        self.memory[addr] = encode_instruction(op, arg)
        
        if op in (Opcode.PUSH, Opcode.JMP, Opcode.JZ, Opcode.CALL, Opcode.NEXT):
            self.machine_code.append(f"{addr:04X} - {op.name} {arg}")
        else:
            self.machine_code.append(f"{addr:04X} - {op.name}")
            
        if is_data:
            self.data_refs.append(addr)
        self.pc += 1
        return addr

    def backpatch(self, addr, target):
        op, _ = decode_instruction(self.memory[addr])
        self.memory[addr] = encode_instruction(op, target)
        for i, line in enumerate(self.machine_code):
            if line.startswith(f"{addr:04X}"):
                if op in (Opcode.PUSH, Opcode.JMP, Opcode.JZ, Opcode.CALL, Opcode.NEXT):
                    self.machine_code[i] = f"{addr:04X} - {op.name} {target}"
                else:
                    self.machine_code[i] = f"{addr:04X} - {op.name}"

    def compile(self, ast: Program):

        jmp_init = self.emit(Opcode.JMP, 0)
        
        self.memory[VECTOR_IO] = encode_instruction(Opcode.IRET)
        self.memory[VECTOR_SO_DATA] = encode_instruction(Opcode.IRET)
        self.memory[VECTOR_SO_RET] = encode_instruction(Opcode.IRET)

        self.backpatch(jmp_init, self.pc)
        for stmt in ast.statements:
            if isinstance(stmt, GlobalVarDecl):
                self.gen_stmt(stmt)
                
        jmp_main = self.emit(Opcode.JMP, 0)

        for stmt in ast.statements:
            if isinstance(stmt, FuncDecl):
                self.function_types[stmt.name] = stmt.ret_type
        
        for stmt in ast.statements:
            if isinstance(stmt, FuncDecl):
                self.functions[stmt.name] = self.pc
                if stmt.name == 'main': self.backpatch(jmp_main, self.pc)
                
                for vtype, arg_name in reversed(stmt.args):
                    if arg_name not in self.symbols:
                        self.symbols[arg_name] = {'addr': self.next_data, 'type': vtype}
                        self.next_data += 1
                        self.data_memory.append(0)
                    self.emit(Opcode.PUSH, self.symbols[arg_name]['addr'], is_data=True)
                    self.emit(Opcode.STORE)
                
                self.gen_stmt(stmt.body)
                
                if stmt.name == 'main':
                    self.emit(Opcode.HALT)
                else:
                    if stmt.ret_type is not None:
                        self.emit(Opcode.PUSH, 0)
                    self.emit(Opcode.RET)
                    
            elif isinstance(stmt, InterruptDecl):
                handler_addr = self.pc
                self.gen_stmt(stmt.body)
                self.emit(Opcode.IRET)
                
                if stmt.name == 'io': self.memory[VECTOR_IO] = encode_instruction(Opcode.JMP, handler_addr)
                elif stmt.name == 'so_data': self.memory[VECTOR_SO_DATA] = encode_instruction(Opcode.JMP, handler_addr)
                elif stmt.name == 'so_ret': self.memory[VECTOR_SO_RET] = encode_instruction(Opcode.JMP, handler_addr)
                
        # backpatching here
        
        for addr, name in self.unresolved_calls:
            if name in self.functions:
                self.backpatch(addr, self.functions[name])

        data_start_addr =  DATA_START # start writing data


        for addr in self.data_refs:
            op, old_arg = decode_instruction(self.memory[addr])
            new_arg = old_arg + data_start_addr
            self.backpatch(addr, new_arg)

        for i, val in enumerate(self.data_memory):
            self.memory[data_start_addr + i] = val
                
        return self.memory, self.machine_code, data_start_addr

    def gen_stmt(self, node):
        if isinstance(node, (GlobalVarDecl, VarDecl)):
            self.symbols[node.name] = {'addr': self.next_data, 'type': node.vtype}
            if node.vtype == 'long':
                self.next_data += 2; self.data_memory.extend([0, 0])
            else:
                self.next_data += 1; self.data_memory.append(0)

            t = self.gen_expr(node.expr)
            if node.vtype == 'long' and t != 'long':
                self.emit(Opcode.SEXT)             # выравниваем int -> long
            self.emit(Opcode.PUSH, self.symbols[node.name]['addr'], is_data=True)
            if node.vtype == 'long':
                self.emit(Opcode.SEAM); self.emit(Opcode.STORE); self.emit(Opcode.CEAM)
            else:
                self.emit(Opcode.STORE)

        elif isinstance(node, Assign):
            t = self.gen_expr(node.expr)
            info = self.symbols[node.name]
            if info['type'] == 'long' and t != 'long':
                self.emit(Opcode.SEXT)
            self.emit(Opcode.PUSH, info['addr'], is_data=True)
            if info['type'] == 'long':
                self.emit(Opcode.SEAM); self.emit(Opcode.STORE); self.emit(Opcode.CEAM)
            else:
                self.emit(Opcode.STORE)
            
        elif isinstance(node, DerefAssign):
            self.gen_expr(node.val_expr)
            self.gen_expr(node.ptr_expr)
            self.emit(Opcode.STORE)

        elif isinstance(node, Block):
            for s in node.statements: self.gen_stmt(s)
            
        elif isinstance(node, EnableInterrupts): self.emit(Opcode.EI)
        elif isinstance(node, DisableInterrupts): self.emit(Opcode.DI)
            
        elif isinstance(node, If):
            self.gen_expr(node.cond)
            jz_addr = self.emit(Opcode.JZ, 0)
            self.gen_stmt(node.true_block)
            jmp_addr = self.emit(Opcode.JMP, 0)
            self.backpatch(jz_addr, self.pc)
            self.gen_stmt(node.else_block)
            self.backpatch(jmp_addr, self.pc)
            
        elif isinstance(node, While):
            start_pc = self.pc
            self.gen_expr(node.cond)
            jz_addr = self.emit(Opcode.JZ, 0)
            self.gen_stmt(node.body)
            self.emit(Opcode.JMP, start_pc)
            self.backpatch(jz_addr, self.pc)
            
        # FOR

        elif isinstance(node, For):
            is_optimizable = False
            var_name = None
            init_expr = None
            limit_expr = None

            if isinstance(node.init, VarDecl):
                var_name = node.init.name
                init_expr = node.init.expr

            elif isinstance(node.init, Assign):
                var_name = node.init.name
                init_expr = node.init.expr


            # CHECK IF THE CODE OPTIMIZABLE WITH "NEXT" INSTRUCTION
            if var_name and isinstance(node.cond, BinOp) and node.cond.op == '<':

                if isinstance(node.cond.left, Var) and node.cond.left.name == var_name:

                    limit_expr = node.cond.right

                    if isinstance(node.step, Assign) and node.step.name == var_name:

                        if isinstance(node.step.expr, BinOp) and node.step.expr.op == '+':
                            left_var = isinstance(node.step.expr.left, Var) and node.step.expr.left.name == var_name

                            right_one = isinstance(node.step.expr.right, Literal) and node.step.expr.right.value == 1

                            if left_var and right_one:

                                is_optimizable = True

            if is_optimizable:

                self.gen_stmt(node.init) 

                self.gen_expr(limit_expr)
                self.gen_expr(init_expr) 
                self.emit(Opcode.SUB)

                self.emit(Opcode.DUP)
                jz_end = self.emit(Opcode.JZ, 0) # if iter <= 0, skip

                self.emit(Opcode.TOR)     # TOS -> R
                start_pc = self.pc

                self.gen_stmt(node.body)
                self.gen_stmt(node.step)  # (i=i+1)

                self.emit(Opcode.NEXT, start_pc)
                
                self.backpatch(jz_end, self.pc)

            else:
                self.gen_stmt(node.init)

                start_pc = self.pc

                self.gen_expr(node.cond)

                jz_addr = self.emit(Opcode.JZ, 0)
                
                self.gen_stmt(node.body)
                self.gen_stmt(node.step)

                self.emit(Opcode.JMP, start_pc)

                self.backpatch(jz_addr, self.pc)

            
        elif isinstance(node, Print):
            expr_type = self.gen_expr(node.expr) # Получаем тип выражения
            if expr_type == 'string':
                
                loop_start = self.pc
                self.emit(Opcode.DUP)       # [ptr, ptr]
                self.emit(Opcode.LOAD)      # [ptr, char]
                self.emit(Opcode.DUP)       # [ptr, char, char]
                jz_end = self.emit(Opcode.JZ, 0)
                self.emit(Opcode.PUSH, MMIO_OUTPUT_CHAR)
                self.emit(Opcode.STORE) 
                self.emit(Opcode.PUSH, 1)
                self.emit(Opcode.ADD)       # ptr = ptr + 1
                self.emit(Opcode.JMP, loop_start)
                
                self.backpatch(jz_end, self.pc)
                self.emit(Opcode.DROP)     
                self.emit(Opcode.DROP)  
            else:
                port = MMIO_OUTPUT_FLOAT if expr_type in ('float','double') else (MMIO_OUTPUT_CHAR if expr_type=='char' else MMIO_OUTPUT_NUM)
                self.emit(Opcode.PUSH, port)
                if expr_type == 'long':
                    self.emit(Opcode.SEAM); self.emit(Opcode.STORE); self.emit(Opcode.CEAM)
                else:
                    self.emit(Opcode.STORE)

        elif isinstance(node, Return):
            if node.expr: 
                self.gen_expr(node.expr)
            self.emit(Opcode.RET)
            
        elif isinstance(node, Call):
            self.gen_expr(node)

            if self.function_types.get(node.name) is not None:
                self.emit(Opcode.DROP)

        elif isinstance(node, Exit):
            self.emit(Opcode.HALT)

    def gen_expr(self, node):
        
        if isinstance(node, Call):
            
            for arg in node.args:
                self.gen_expr(arg)
            call_addr = self.emit(Opcode.CALL, 0)
            self.unresolved_calls.append((call_addr, node.name))
        
            return self.function_types.get(node.name)

        if isinstance(node, ReadChar):
            self.emit(Opcode.PUSH, MMIO_INPUT)
            self.emit(Opcode.LOAD)
            return 'char'
        
        if isinstance(node, ArrayAlloc):
            ptr = self.next_data
            self.next_data += node.size
            for _ in range(node.size):
                self.data_memory.append(0)
            self.emit(Opcode.PUSH, ptr, is_data=True)
            return node.vtype + '*'
            
        if isinstance(node, Deref):
            t = self.gen_expr(node.expr)
            self.emit(Opcode.LOAD)  
            if isinstance(t, str) and t.endswith('*'):
                return t[:-1]
            return t

        if isinstance(node, Literal):
            if node.vtype in ('float', 'double'):
                float_ptr = self.next_data
                self.data_memory.append(float_to_bits(node.value))
                self.next_data += 1
                self.emit(Opcode.PUSH, float_ptr, is_data=True)
                self.emit(Opcode.LOAD)
            elif node.vtype == 'string':
                str_ptr = self.next_data
                for char in node.value:
                    self.data_memory.append(ord(char))
                    self.next_data += 1
                self.data_memory.append(0)
                self.next_data += 1
                self.emit(Opcode.PUSH, str_ptr, is_data=True)
            elif node.vtype == 'long':
                lo = node.value & 0xFFFFFFFF
                hi = (node.value >> 32) & 0xFFFFFFFF
                ptr = self.next_data
                self.data_memory.extend([to_signed32(lo), to_signed32(hi)])
                self.next_data += 2
                self.emit(Opcode.PUSH, ptr, is_data=True)
                self.emit(Opcode.SEAM); self.emit(Opcode.LOAD); self.emit(Opcode.CEAM)
                return 'long'
            else:
                self.emit(Opcode.PUSH, node.value)
            return node.vtype
            
        elif isinstance(node, Var):
            var_info = self.symbols[node.name]
            self.emit(Opcode.PUSH, var_info['addr'], is_data=True)
            if var_info['type'] == 'long':
                self.emit(Opcode.SEAM); self.emit(Opcode.LOAD); self.emit(Opcode.CEAM)
            else:
                self.emit(Opcode.LOAD)
            return var_info['type']
            
        elif isinstance(node, UnaryOp):
            t = self.gen_expr(node.expr)
            if node.op == '!':
                self.emit(Opcode.PUSH, 0)
                self.emit(Opcode.CMP)
            elif node.op == 'not':
                self.emit(Opcode.NOT)
            return t
            
        elif isinstance(node, BinOp):
            t_left = self.gen_expr(node.left)

            if t_left == 'long' and node.op in ('+', '-', '*'):
                t_right = self.gen_expr(node.right)
                if t_right != 'long':
                    self.emit(Opcode.SEXT)
                self.emit(Opcode.SEAM)
                if   node.op == '+': self.emit(Opcode.ADD)
                elif node.op == '-': self.emit(Opcode.SUB)
                elif node.op == '*': self.emit(Opcode.MUL)
                self.emit(Opcode.CEAM)
                return 'long'

            t_right = self.gen_expr(node.right)
            is_float = t_left in ('float', 'double')
            
            if node.op == '+': self.emit(Opcode.FADD if is_float else Opcode.ADD)
            elif node.op == '-': self.emit(Opcode.FSUB if is_float else Opcode.SUB)
            elif node.op == '*': self.emit(Opcode.FMUL if is_float else Opcode.MUL)
            elif node.op == '/': self.emit(Opcode.FDIV if is_float else Opcode.DIV)
            
            elif node.op == 'and': self.emit(Opcode.AND)
            elif node.op == 'or': self.emit(Opcode.OR)
            elif node.op == 'xor': self.emit(Opcode.XOR)
            elif node.op == '<<': self.emit(Opcode.SHL)
            elif node.op == '>>': self.emit(Opcode.SHR)
            
            elif node.op == '==': self.emit(Opcode.CMP)
            elif node.op == '!=': self.emit(Opcode.NEQ)
            elif node.op == '>': self.emit(Opcode.GT)
            elif node.op == '<': self.emit(Opcode.LT)
            return 'boolean' if node.op in ('==', '!=', '>', '<') else t_left