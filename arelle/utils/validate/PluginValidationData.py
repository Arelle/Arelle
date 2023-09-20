from dataclasses import dataclass


@dataclass
class PluginValidationData:
    """
    Base dataclass which should be extended with fields by plugins that need to cache data between validation rules.
    """
    name: str
