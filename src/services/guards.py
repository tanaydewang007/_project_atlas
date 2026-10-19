import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


class OutputGuard:
    def redact(self, text: str) -> str:
        return EMAIL.sub("[redacted]", text)
