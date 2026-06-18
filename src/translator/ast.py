class ASTNode: pass
class Program(ASTNode):
    def __init__(self, stmts): self.statements = stmts
class Block(ASTNode):
    def __init__(self, stmts): self.statements = stmts
class VarDecl(ASTNode):
    def __init__(self, vtype, name, expr): self.vtype, self.name, self.expr = vtype, name, expr
class GlobalVarDecl(ASTNode):
    def __init__(self, vtype, name, expr): self.vtype, self.name, self.expr = vtype, name, expr
class Assign(ASTNode):
    def __init__(self, name, expr): self.name, self.expr = name, expr
class DerefAssign(ASTNode):
    def __init__(self, ptr_expr, val_expr): self.ptr_expr, self.val_expr = ptr_expr, val_expr
class If(ASTNode):
    def __init__(self, cond, true_block, else_block): self.cond, self.true_block, self.else_block = cond, true_block, else_block
class While(ASTNode):
    def __init__(self, cond, body): self.cond, self.body = cond, body
class For(ASTNode):
    def __init__(self, init, cond, step, body): self.init, self.cond, self.step, self.body = init, cond, step, body
class Print(ASTNode):
    def __init__(self, expr): self.expr = expr
class InterruptDecl(ASTNode):
    def __init__(self, name, body): self.name, self.body = name, body
class EnableInterrupts(ASTNode): pass
class DisableInterrupts(ASTNode): pass
class BinOp(ASTNode):
    def __init__(self, left, op, right): self.left, self.op, self.right = left, op, right
class UnaryOp(ASTNode):
    def __init__(self, op, expr): self.op, self.expr = op, expr
class Var(ASTNode):
    def __init__(self, name): self.name = name
class Deref(ASTNode):
    def __init__(self, expr): self.expr = expr
class Literal(ASTNode):
    def __init__(self, vtype, value): self.vtype, self.value = vtype, value
class ArrayAlloc(ASTNode):
    def __init__(self, vtype, size): self.vtype, self.size = vtype, size
class ReadChar(ASTNode): pass
class FuncDecl(ASTNode):
    def __init__(self, name, args, ret_type, body): self.name, self.args, self.ret_type, self.body = name, args, ret_type, body
class Call(ASTNode):
    def __init__(self, name, args): self.name, self.args = name, args
class Return(ASTNode):
    def __init__(self, expr): self.expr = expr
class Exit(ASTNode): pass