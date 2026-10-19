import chromadb

from src.models.domain import Chunk
from src.services.embedder import Embedder


class VectorStore:
    def __init__(self, path: str, embedder: Embedder) -> None:
        self.embedder = embedder
        client = chromadb.PersistentClient(path=path) if path != ":memory:" else chromadb.EphemeralClient()
        self.collection = client.get_or_create_collection(
            f"reports_{embedder.backend}", metadata={"hnsw:space": "cosine"}, embedding_function=None
        )

    def count(self) -> int:
        return self.collection.count()

    def report_chunk_count(self, report_id: str) -> int:
        return len(self.collection.get(where={"report_id": report_id}, include=[])["ids"])

    def report_chunks(self, report_id: str) -> list[Chunk]:
        found = self.collection.get(where={"report_id": report_id}, include=["documents", "metadatas"])
        chunks = [Chunk(i, report_id, int(m["page"]), doc) for i, doc, m in zip(found["ids"], found["documents"], found["metadatas"])]
        return sorted(chunks, key=lambda c: (c.page, c.id))

    def delete_report(self, report_id: str) -> None:
        self.collection.delete(where={"report_id": report_id})

    def upsert(self, chunks: list[Chunk], metas: dict[str, dict]) -> None:
        if not chunks:
            return
        texts = [c.text for c in chunks]
        self.collection.upsert(
            ids=[c.id for c in chunks],
            documents=texts,
            embeddings=self.embedder.embed(texts),
            metadatas=[{"report_id": c.report_id, "page": c.page, **metas[c.id]} for c in chunks],
        )

    def search(self, query: str, report_ids: list[str], k: int) -> list[Chunk]:
        if not report_ids or self.count() == 0:
            return []
        result = self.collection.query(
            query_embeddings=self.embedder.embed([query]),
            n_results=k,
            where={"report_id": {"$in": report_ids}},
            include=["documents", "metadatas", "distances"],
        )
        return [
            Chunk(id, meta["report_id"], int(meta["page"]), doc, 1.0 - dist)
            for id, doc, meta, dist in zip(result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0])
        ]

    def page_chunks(self, report_id: str, page: int) -> list[Chunk]:
        result = self.collection.get(where={"$and": [{"report_id": report_id}, {"page": page}]}, include=["documents", "metadatas"])
        return [Chunk(id, report_id, page, doc) for id, doc in zip(result["ids"], result["documents"])]
