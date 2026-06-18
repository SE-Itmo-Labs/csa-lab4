from .ast import *

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def current(self): return self.tokens[self.pos] if self.pos < len(self.tokens) else ('EOF', '')
    def match(self, kind, val=None):
        c = self.current()
        if c[0] == kind and (val is None or c[1] == val):
            self.pos += 1
            return c[1]
        return None
    def expect(self, kind, val=None):
        c = self.current()
        if c[0] == kind and (val is None or c[1] == val):
            self.pos += 1
            return c[1]
        raise SyntaxError(f"Expected {kind}:{val}, got {c}")

    def parse(self):
        stmts = []
        while self.current()[0] != 'EOF':
            if self.match('KEYWORD', 'interrupt'):
                name = self.expect('ID')
                self.expect('PUNCT', '(')
                body = []
                while not self.match('PUNCT', ')'):
                    body.append(self.parse_statement())
                stmts.append(InterruptDecl(name, Block(body)))

            elif self.match('KEYWORD', 'global'):
                vtype = self.expect('KEYWORD')
                
                # Обработка global char[100] name
                # Если видим '[', значит это аллокация массива
                if self.current()[1] == '[':
                    self.expect('PUNCT', '[')
                    size = int(self.expect('INT'))
                    self.expect('PUNCT', ']')
                    name = self.expect('ID')

                    expr = ArrayAlloc(vtype, size)
                    vtype += '*'
                else:
                    # Обычный формат: global integer flag = 1
                    if self.match('OP', '*'): vtype += '*'
                    name = self.expect('ID')
                    self.expect('OP', '=')
                    expr = self.parse_expr()
                    
                stmts.append(GlobalVarDecl(vtype, name, expr))

            elif self.current()[0] == 'PUNCT' and self.current()[1] == '{':
                self.expect('PUNCT', '{')
                args = []
                while not self.match('PUNCT', '}'):
                    vtype = self.expect('KEYWORD')
                    arg_name = self.expect('ID')
                    args.append((vtype, arg_name))
                    self.match('PUNCT', ';')
                    self.match('PUNCT', ',')
                
                ret_type = None
                if self.current()[0] == 'KEYWORD' and self.current()[1] in ('integer', 'float', 'boolean', 'long', 'char', 'string'):
                    ret_type = self.expect('KEYWORD')
                
                name = self.expect('ID')
                self.expect('PUNCT', '(')
                body = []
                while not self.match('PUNCT', ')'):
                    body.append(self.parse_statement())
                stmts.append(FuncDecl(name, args, ret_type, Block(body)))
            else:
                # self.pos += 1 !!!
                raise SyntaxError(f"Unexpected top-level token: {self.current()}")
        return Program(stmts)

    def parse_statement(self):
        if self.current()[0] == 'KEYWORD' and self.current()[1] in ('integer', 'float', 'long', 'boolean', 'char', 'string'):
            vtype = self.expect('KEYWORD')
            name = self.expect('ID')
            self.expect('OP', '=')
            expr = self.parse_expr()
            return VarDecl(vtype, name, expr)
        elif self.match('KEYWORD', 'print'):
            self.expect('PUNCT', '('); expr = self.parse_expr(); self.expect('PUNCT', ')')
            return Print(expr)
        elif self.match('KEYWORD', 'enable_interrupts'):
            self.expect('PUNCT', '('); self.expect('PUNCT', ')')
            return EnableInterrupts()
        elif self.match('KEYWORD', 'disable_interrupts'):
            self.expect('PUNCT', '('); self.expect('PUNCT', ')')
            return DisableInterrupts()
        elif self.match('KEYWORD', 'exit'):
            self.expect('PUNCT', '('); self.expect('PUNCT', ')')
            return Exit()
        elif self.match('KEYWORD', 'if'):
            self.expect('PUNCT', '{'); cond = self.parse_expr(); self.expect('PUNCT', '}')
            self.expect('PUNCT', '(')
            true_block = []
            while not self.match('PUNCT', ')'): true_block.append(self.parse_statement())
            else_block = []
            if self.match('KEYWORD', 'else'):
                self.expect('PUNCT', '(')
                while not self.match('PUNCT', ')'): else_block.append(self.parse_statement())
            return If(cond, Block(true_block), Block(else_block))
        elif self.match('KEYWORD', 'while'):
            self.expect('PUNCT', '{'); cond = self.parse_expr(); self.expect('PUNCT', '}')
            self.expect('PUNCT', '(')
            body = []
            while not self.match('PUNCT', ')'): body.append(self.parse_statement())
            return While(cond, Block(body))
        elif self.match('KEYWORD', 'for'):
            self.expect('PUNCT', '{'); init = self.parse_statement(); self.expect('PUNCT', ':')
            cond = self.parse_expr(); self.expect('PUNCT', ':')
            step = self.parse_statement(); self.expect('PUNCT', '}')
            self.expect('PUNCT', '(')
            body = []
            while not self.match('PUNCT', ')'): body.append(self.parse_statement())
            return For(init, cond, step, Block(body))

        elif self.match('KEYWORD', 'return'):
            expr = self.parse_expr() if self.current()[0] != 'PUNCT' else None
            return Return(expr)
        elif self.current()[0] == 'ID':
            name = self.expect('ID')

            if self.match('OP', '&'): 
                self.expect('OP', '=')
                expr = self.parse_expr()
                return DerefAssign(Var(name), expr)

            if self.match('PUNCT', '('):
                args = []
                while not self.match('PUNCT', ')'):
                    args.append(self.parse_expr())
                    self.match('PUNCT', ',')
                return Call(name, args)
            
            self.expect('OP', '=')
            expr = self.parse_expr()
            return Assign(name, expr)
        raise SyntaxError(f"Unexpected token {self.current()}")

    # Простой парсер выражений (с учетом приоритетов)
    
    def parse_expr(self): return self.parse_equality()

    def parse_bitwise_or(self):
        left = self.parse_bitwise_xor()
        while self.current()[1] == 'or':
            op = self.expect('KEYWORD')
            right = self.parse_bitwise_xor()
            left = BinOp(left, op, right)
        return left

    def parse_bitwise_xor(self):
        left = self.parse_bitwise_and()
        while self.current()[1] == 'xor':
            op = self.expect('KEYWORD')
            right = self.parse_bitwise_and()
            left = BinOp(left, op, right)
        return left

    def parse_bitwise_and(self):
        left = self.parse_equality()
        while self.current()[1] == 'and':
            op = self.expect('KEYWORD')
            right = self.parse_equality()
            left = BinOp(left, op, right)
        return left

    def parse_equality(self):
        left = self.parse_shift()
        while self.current()[1] in ('==', '!=', '<', '>'):
            op = self.expect('OP')
            right = self.parse_shift()
            left = BinOp(left, op, right)
        return left

    def parse_shift(self):
        left = self.parse_add_sub()
        while self.current()[1] in ('<<', '>>'):
            op = self.expect('OP')
            right = self.parse_add_sub()
            left = BinOp(left, op, right)
        return left
    
    def parse_add_sub(self):
        left = self.parse_mul_div()
        while self.current()[1] in ('+', '-'):
            op = self.expect('OP')
            right = self.parse_mul_div()
            left = BinOp(left, op, right)
        return left
    

    def parse_mul_div(self):
        left = self.parse_factor()
        while self.current()[1] in ('*', '/'):
            op = self.expect('OP')
            right = self.parse_factor()
            left = BinOp(left, op, right)
        return left
    

    def parse_factor(self):

        if self.current()[0] == 'LONG':
            v = self.expect('LONG')
            return Literal('long', int(v[:-1]))
        
        if self.match('OP', '!'): return UnaryOp('!', self.parse_factor())
        
        if self.current()[1] == 'not':
            self.expect('KEYWORD')
            return UnaryOp('not', self.parse_factor())

        if self.current()[1] == 'read_char':
            self.match('KEYWORD')
            self.expect('PUNCT', '(')
            self.expect('PUNCT', ')')
            return ReadChar()

        c = self.current()

        if c[0] == 'KEYWORD' and c[1] in ('integer', 'long', 'float', 'double', 'boolean', 'char', 'string'):
            btype = self.expect('KEYWORD')
            self.expect('PUNCT', '[')
            size = int(self.expect('INT'))
            self.expect('PUNCT', ']')
            return ArrayAlloc(btype, size)

        if self.match('INT'): return Literal('integer', int(c[1]))

        elif self.match('FLOAT'): return Literal('float', float(c[1].replace('f', '')))

        elif self.match('HEX'): return Literal('integer', int(c[1], 16))

        elif self.match('BOOL'): return Literal('boolean', 1 if c[1] == 'TRUE' else 0)

        
        # ОБРАБОТКА \n В СТРОКАХ:
        elif self.match('STRING'): 
            val = c[1].strip("'").encode('utf-8').decode('unicode_escape')
            return Literal('string', val)
        elif self.current()[0] == 'ID': 
            name = self.expect('ID')
            if self.match('PUNCT', '('):
                args = []
                while not self.match('PUNCT', ')'):
                    args.append(self.parse_expr())
                    self.match('PUNCT', ',')
                return Call(name, args)
            
            var_node = Var(name)

            if self.match('OP', '&'):
                return Deref(var_node)
            
            return var_node

        raise SyntaxError(f"Bad factor {c}")

def print_ast(node, indent=""):

    if node is None: return

    name = type(node).__name__
    
    if isinstance(node, (Program, Block)):
        print(indent + f"{name}:")
        for s in node.statements: print_ast(s, indent + "  ")

    elif isinstance(node, FuncDecl):
        print(indent + f"Func({node.name} ret:{node.ret_type}):")
        print_ast(node.body, indent + "  ")

    elif isinstance(node, (EnableInterrupts, DisableInterrupts, ReadChar, Exit)): 
        print(indent + f"{name}()")

    elif isinstance(node, GlobalVarDecl):
        print(indent + f"GlobalVar({node.vtype} {node.name}):")
        print_ast(node.expr, indent + "  ")

    elif isinstance(node, VarDecl):
        print(indent + f"VarDecl({node.vtype} {node.name}):")
        print_ast(node.expr, indent + "  ")

    elif isinstance(node, InterruptDecl):
        print(indent + f"Interrupt({node.name}):")
        print_ast(node.body, indent + "  ")

    elif isinstance(node, ArrayAlloc):
        print(indent + f"ArrayAlloc({node.vtype}[{node.size}])")

    elif isinstance(node, Deref):
        print(indent + "Deref(&):")
        print_ast(node.expr, indent + "  ")

    elif isinstance(node, Assign):
        print(indent + f"Assign({node.name}):"); print_ast(node.expr, indent + "  ")

    elif isinstance(node, BinOp):
        print(indent + f"BinOp({node.op}):"); print_ast(node.left, indent+"  "); print_ast(node.right, indent+"  ")

    elif isinstance(node, Print):
        print(indent + "Print:"); print_ast(node.expr, indent + "  ")

    elif isinstance(node, If):
        print(indent + "If:"); print_ast(node.cond, indent+"  "); print_ast(node.true_block, indent+"  "); print_ast(node.else_block, indent+"  ")

    elif isinstance(node, While):
        print(indent + "While:"); print_ast(node.cond, indent+"  "); print_ast(node.body, indent+"  ")

    elif isinstance(node, For):
        print(indent + "For:"); print_ast(node.init, indent+"  "); print_ast(node.cond, indent+"  "); print_ast(node.step, indent+"  "); print_ast(node.body, indent+"  ")

    elif isinstance(node, Literal): 
        safe_val = repr(node.value) if node.vtype == 'string' else node.value
        print(indent + f"Literal({node.vtype}: {safe_val})")

    elif isinstance(node, Var): print(indent + f"Var({node.name})")

    elif isinstance(node, (EnableInterrupts, DisableInterrupts)): print(indent + f"{name}()")