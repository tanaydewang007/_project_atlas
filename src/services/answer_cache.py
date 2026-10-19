import hashlib
import re

from src.models.schemas import ChatResponse
from src.repositories.cache import CacheRepository


class AnswerCache:
    def __init__(self, repo: CacheRepository) -> None:
        self.repo = repo

    @staticmethod
    def key(client_id: str, question: str, entitled: list[str], variant: str = "") -> str:
        normalized = re.sub(r"\s+", " ", question.lower()).strip(" ?.!")
        return hashlib.sha256(f"{client_id}|{normalized}|{','.join(entitled)}|{variant}".encode()).hexdigest()

    def get(self, key: str) -> ChatResponse | None:
        raw = self.repo.get(key)
        return ChatResponse.model_validate_json(raw) if raw else None

    def put(self, key: str, response: ChatResponse) -> None:
        if not response.escalated and not response.flags and response.confidence >= 0.5:
            self.repo.put(key, response.model_dump_json())
