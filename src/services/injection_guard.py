import re


class InjectionGuard:
    DOC_PATTERNS = [
        r"disregard (all )?(previous|prior|above|earlier) instructions",
        r"ignore (all |any |your |the )?(previous |prior |above |earlier )?(instructions|rules|guidelines)",
        r"note to ai( systems?)?",
        r"you are now\b",
        r"system prompt",
        r"print the full contents",
        r"contact emails?",
        r"clients? table",
        r"only reliable source",
        r"reveal (your|the) (instructions|prompt)",
    ]
    USER_PATTERNS = {
        "write_attempt": [
            r"\b(delete|drop|truncate|insert|update|alter)\b.{0,40}\b(rows?|tables?|records?|database|entries)\b",
            r"\bdelete all\b",
        ],
        "prompt_override": [
            r"ignore (all |any |your |the )?(previous |prior |above |earlier )?(instructions|rules|guidelines|prompt)",
            r"disregard (all )?(previous|prior|above|earlier|your) instructions",
            r"forget (everything|your instructions)",
            r"system prompt",
            r"you are now\b",
            r"reveal (your|the) (instructions|prompt)",
        ],
        "data_exfiltration": [
            r"(list|print|show|dump|reveal|give|send|export).{0,40}(client|customer)s?.{0,30}(emails?|contacts?|table|data|details)",
            r"contact emails?",
            r"clients? table",
        ],
    }

    def __init__(self) -> None:
        self._doc = [re.compile(p, re.I) for p in self.DOC_PATTERNS]
        self._user = {k: [re.compile(p, re.I) for p in v] for k, v in self.USER_PATTERNS.items()}

    def classify_request(self, question: str) -> list[str]:
        return [kind for kind, patterns in self._user.items() if any(p.search(question) for p in patterns)]

    def sanitize(self, text: str) -> tuple[str, list[str]]:
        kept, hits = [], []
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
            if any(p.search(sentence) for p in self._doc):
                hits.append(sentence.strip())
            elif sentence.strip():
                kept.append(sentence.strip())
        return " ".join(kept), hits
