from enum import Enum

class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class FindingStatus(str, Enum):
    OPEN = "open"
    CONFIRMED = "confirmed"
    FIXED = "fixed"
    FALSE_POSITIVE = "false_positive"
