MEMORY_SIZE = 2048          # 32-битные слова
DATA_STACK_SIZE = 64
RETURN_STACK_SIZE = 64

# Прерывания
VECTOR_IO      = 0x0005     # Вектор прерывания ввода-вывода
VECTOR_SO_DATA = 0x0006     # Вектор Data Stack Overflow
VECTOR_SO_RET  = 0x0007     # Вектор Return Stack Overflow

# Разметка памяти
CODE_START = 0x0040         # Начало кода
DATA_START = 0x0400         # Переменные и строки храним здесь (1024)

# MMIO
MMIO_OUTPUT_FLOAT = 0x07FC  # Вывод чисел с плавающей точкой
MMIO_OUTPUT_NUM   = 0x07FD  # Вывод целого числа
MMIO_INPUT        = 0x07FE  # Ввод символа
MMIO_OUTPUT_CHAR  = 0x07FF  # Вывод символа
