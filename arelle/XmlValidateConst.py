'''
See COPYRIGHT.md for copyright information.
'''

UNVALIDATED = 0 # note that these values may be used a constants in code for better efficiency
UNKNOWN = 1
INVALID = 2
NONE = 3
VALID = 4 # values >= VALID are valid
VALID_ID = 5
VALID_NO_CONTENT = 6 # may be a complex type with children, must be last (after VALID with content enums)
