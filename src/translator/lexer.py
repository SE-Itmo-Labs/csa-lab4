import re

def tokenize(code: str):
    token_specification = [
        ('LONG',      r'\d+L'),
        ('FLOAT',     r'\d+\.\d+f|\d+f'),
        ('HEX',       r'0x[0-9a-fA-F]+'),
        ('INT',       r'\d+'),
        ('STRING',    r"'[^']*'"),
        ('BOOL',      r'TRUE|FALSE'),
        ('KEYWORD', r'\b(integer|long|float|double|boolean|char|string|if|elif|else|while|for|print|interrupt|enable_interrupts|disable_interrupts|read_char|return|exit|global|and|or|xor|not)\b'),
        ('ID',        r'[a-zA-Z_]\w*'),
        ('COMMENT',   r'(?<!\\)%.*?(?<!\\)%|(?<!\\)%[^\n]*'),
        ('OP',        r'==|!=|<=|>=|<<|>>|<|>|\+|-|\*|/|!|=|&'),
        ('PUNCT',     r'[{}():;,\[\]]'),
        ('WS',        r'\s+'),
    ]

    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specification)
    tokens = []

    for mo in re.finditer(tok_regex, code):
        kind = mo.lastgroup
        value = mo.group()

        if kind not in ('WS', 'COMMENT'):
            tokens.append((kind, value))
    return tokens