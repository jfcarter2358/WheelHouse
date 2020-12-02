from enum import Enum, unique


class BaseEnum(Enum):
    @classmethod
    def values(cls) -> list:
        """Returns a list of raw values for the class"""
        values = [member.value for role, member in cls.__members__.items()]
        return values

@unique
class Operators(BaseEnum):
    """Represents the conditional operators that are supported"""

    IN                 = 'in'
    EQUAL              = "=="
    NOT_EQUAL          = "!="
    LESS_THAN          = "<"
    GREATER_THAN       = ">"
    LESS_THAN_EQUAL    = '<='
    GREATER_THAN_EQUAL = '>='

@unique
class LogLevel(BaseEnum):
    """Represents the log levels that are supported"""

    NONE  = 0
    ERROR = 1
    WARN  = 2
    INFO  = 3
    DEBUG = 4