import importlib.util
import sys

if importlib.util.find_spec("_decimal") is None:
    # The pure Python decimal module converts through int, so the oversized number tests need the limit lifted.
    sys.set_int_max_str_digits(0)
