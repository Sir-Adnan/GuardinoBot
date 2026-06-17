from enum import Enum


class UserStatusModify(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    ON_HOLD = "on_hold"

    def __str__(self) -> str:
        return str(self.value)
