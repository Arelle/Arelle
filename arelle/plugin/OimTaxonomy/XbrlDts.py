"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Any

from arelle.ModelXbrl import ModelXbrl, create as modelXbrlCreate
from matplotlib._docstring import kwarg_doc

class XbrlDts(ModelXbrl): # complete wrapper for ModelXbrl
    def __init__(self,  *args: Any, **kwargs: Any) -> None:
        super(XbrlDts, self).__init__(*args, **kwargs)
        
    @property
    def xbrlTaxonomy(self):
        return cast(XbrlTaxonomy, self.modelDocument)

def create(*args: Any, **kwargs: Any) -> XbrlDts:
    return cast(XbrlDts, modelXbrlCreate(*args, **kwargs))
