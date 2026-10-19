import re

from src.models.domain import ParsedQuestion


class FollowUp:
    CUE = re.compile(r"^\s*(and|also|what about|how about|same for|now|then|what if|for|in|ok(ay)?,? (and|what about))\b", re.I)
    MAX_WORDS = 8

    @classmethod
    def maybe(cls, question: str) -> bool:
        return len(question.split()) <= cls.MAX_WORDS and (bool(cls.CUE.match(question)) or len(question.split()) <= 6)

    @classmethod
    def applies(cls, question: str, parsed: ParsedQuestion, has_history: bool) -> bool:
        if not has_history or len(question.split()) > cls.MAX_WORDS:
            return False
        if cls.CUE.match(question):
            return True
        has_topic = bool(parsed.topic_ids or parsed.report_ids)
        return not has_topic and bool(parsed.region or parsed.year or parsed.metrics)

    @staticmethod
    def overlay(prev: ParsedQuestion, cur: ParsedQuestion) -> ParsedQuestion:
        has_topic = bool(cur.topic_ids or cur.report_ids)
        return ParsedQuestion(
            report_ids=cur.report_ids if has_topic else prev.report_ids,
            topic_ids=cur.topic_ids if has_topic else prev.topic_ids,
            metric=cur.metric or prev.metric,
            metrics=cur.metrics or prev.metrics,
            region=cur.region or prev.region,
            year=cur.year or prev.year,
            other_region=cur.other_region,
        )
