"""Fallback strtobool implementation compatible with the stdlib distutils version."""


class DistUtils:
    @staticmethod
    def strtobool(val: str) -> bool:
        v = str(val).lower()
        if v in ("y", "yes", "t", "true", "on", "1"):
            return True
        if v in ("n", "no", "f", "false", "off", "0"):
            return False
        raise ValueError(f"invalid truth value {val!r}")
