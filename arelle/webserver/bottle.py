# This is a redirection module that re-exports all symbols from the pip-installed bottle module for backwards
# compatibility from when Arelle commited this file directly instead of using the pip-installed version.
# This is required because external plugin import this file directly.

# Rexport all public symbols from pip-installed bottle
from bottle import *
