import re

from src.models.domain import ParsedQuestion, Report

STOPWORDS = {
    "what", "which", "when", "where", "who", "will", "the", "and", "for", "from", "with", "about", "global", "market",
    "markets", "report", "reports", "size", "worth", "value", "valued", "cagr", "industry", "outlook", "share", "region",
    "year", "years", "how", "much", "big", "does", "did", "our", "your", "you", "can", "should", "trust", "between",
    "than", "this", "that", "its", "have", "has", "tell", "give", "show", "expected", "forecast", "projected", "growth",
    "rate", "estimate", "was", "main", "key", "were", "are", "next", "last", "world", "worldwide", "apac", "asia", "pacific",
}
FILLER = {"rough", "guess", "pleas", "batao", "bata", "kitna", "dono", "tell", "mein", "hoga", "quick", "brief", "short", "simpl", "just", "europ", "north", "latin", "middl", "afric", "india", "china", "japan", "unite", "state", "bigge", "large", "small", "great", "worth", "valu"}
COMPARE_SPLIT = r"\b(?:than|versus|vs\.?|compared (?:to|with)|against)\b"
OTHER_REGIONS = r"europe|north america|latin america|middle east|africa|india|china|japan|united states"


def stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 2 and w not in STOPWORDS}


class QuestionParser:
    def parse(self, question: str, reports: list[Report]) -> ParsedQuestion:
        q = question.lower()
        parsed = ParsedQuestion()
        parsed.report_ids = sorted({f"R-{n}" for n in re.findall(r"\br-?(\d{3})\b", q)})
        years = [int(y) for y in re.findall(r"\b(20\d{2})\b", q)]
        parsed.year = max(years) if years else None
        if re.search(r"\b(apac|asia[- ]pacific|asia)\b", q):
            parsed.region = "APAC"
        elif re.search(r"\b(global|worldwide|world)\b", q):
            parsed.region = "Global"
        other = re.search(rf"\b({OTHER_REGIONS})\b", q)
        parsed.other_region = other.group(1) if other and parsed.region is None else None
        if re.search(r"cagr|growth rate|growing|compound annual", q):
            parsed.metrics.append("CAGR")
        if re.search(r"\bshare\b|percent|proportion|%|split|breakdown|distribution", q):
            parsed.metrics.append("Regional share")
        if re.search(r"market size|\bsize\b|worth|\bvalue\b|valued|revenue|how big|market be|market to be|bigger|larger|smaller|greater", q):
            parsed.metrics.append("Market size")
        parsed.metric = parsed.metrics[0] if parsed.metrics else None
        if parsed.report_ids:
            return parsed
        parsed.topic_ids = self._best(stems(question), reports)
        known = set().union(*(stems(r.title) for r in reports)) | FILLER
        parsed.unknown = len({w for w in stems(question) if w not in known and len(w) > 3})
        groups = [g for g in (self._best(stems(part), reports) for part in re.split(COMPARE_SPLIT, q)) if g]
        if len(re.split(COMPARE_SPLIT, q)) > 1 and len(groups) >= 2:
            parsed.topic_ids = sorted(set().union(*groups))
        by_publisher = self._publisher_ids(q, reports)
        if by_publisher is not None:
            parsed.topic_ids = [i for i in (parsed.topic_ids or [r.id for r in reports]) if i in by_publisher]
        return parsed

    @staticmethod
    def _best(wanted: set[str], reports: list[Report]) -> list[str]:
        scores = {r.id: len(wanted & stems(r.title)) for r in reports}
        best = max(scores.values(), default=0)
        return sorted(rid for rid, s in scores.items() if best >= 1 and s == best)

    @staticmethod
    def _publisher_ids(q: str, reports: list[Report]) -> list[str] | None:
        if re.search(r"third[- ]party|independent|aquila", q):
            return [r.id for r in reports if "third party" in r.publisher.lower() or "aquila" in r.publisher.lower()]
        if re.search(r"\bcmr\b", q):
            return [r.id for r in reports if r.publisher == "CMR"]
        if re.search(r"public (excerpt|report)", q):
            return [r.id for r in reports if r.is_public]
        return None
