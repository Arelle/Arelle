import sys

__VERSION__ = '0.7.5'  # HF: patched to 0.7.5

from arelle.xlwt.Workbook import Workbook
from arelle.xlwt.Worksheet import Worksheet
from arelle.xlwt.Row import Row
from arelle.xlwt.Column import Column
from arelle.xlwt.Formatting import Font, Alignment, Borders, Pattern, Protection
from arelle.xlwt.Style import XFStyle, easyxf, add_palette_colour
from arelle.xlwt.ExcelFormula import *
