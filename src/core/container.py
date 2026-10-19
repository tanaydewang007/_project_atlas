import logging

from src.agents.graph import AgentGraph
from src.agents.nodes.calculator import CalculatorNode
from src.agents.nodes.critic import CriticNode
from src.agents.nodes.escalation import EscalationNode
from src.agents.nodes.retriever import RetrieverNode
from src.agents.nodes.router import RouterNode
from src.agents.nodes.writer import WriterNode
from src.agents.renderer import AnswerRenderer
from src.core.config import Settings
from src.db.database import Database
from src.db.seed import Seeder
from src.repositories.audit import AuditRepository
from src.repositories.cache import CacheRepository
from src.repositories.clients import ClientRepository
from src.repositories.conversations import ConversationRepository
from src.repositories.escalations import EscalationRepository
from src.repositories.reports import ReportRepository
from src.services.answer_cache import AnswerCache
from src.services.calculator import CalculatorService
from src.services.chat import ChatService
from src.services.chunker import Chunker
from src.services.citations import CitationService
from src.services.confidence import ConfidenceScorer
from src.services.embedder import Embedder
from src.services.entitlement import EntitlementService
from src.services.guards import OutputGuard
from src.services.ingestion import IngestionService
from src.services.injection_guard import InjectionGuard
from src.services.llm import LLMService
from src.services.question_parser import QuestionParser
from src.services.report_admin import ReportAdminService
from src.services.sql_planner import SqlPlanner
from src.services.sql_tool import SqlToolService
from src.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db = Database(settings.db_path)
        self.db.init_schema()
        Seeder(self.db).run()

        self.reports = ReportRepository(self.db)
        self.clients = ClientRepository(self.db)
        self.escalations = EscalationRepository(self.db)
        self.conversations = ConversationRepository(self.db)
        self.audit = AuditRepository(self.db)

        self.llm = LLMService(settings)
        self.embedder = Embedder(settings.embedding_backend)
        self.store = VectorStore(settings.chroma_path, self.embedder)
        self.guard = InjectionGuard()
        self.entitlement = EntitlementService(self.clients, self.reports)
        self.sql_tool = SqlToolService(settings, self.reports, self.entitlement)
        self.planner = SqlPlanner(self.llm)
        self.ingestion = IngestionService(
            settings, self.reports, self.store, Chunker(settings.chunk_chars, settings.chunk_overlap), self.guard, self.audit
        )

        cache_repo = CacheRepository(self.db, settings.cache_ttl_s)
        self.report_admin = ReportAdminService(settings, self.reports, self.clients, self.store, self.ingestion, cache_repo, self.guard)
        citations = CitationService(self.store, self.reports, self.guard)
        graph = AgentGraph(
            RouterNode(self.llm, self.guard, QuestionParser(), self.planner, self.reports, self.audit, self.clients, self.entitlement),
            RetrieverNode(self.llm, settings, self.entitlement, self.reports, self.store, self.sql_tool, self.planner, self.guard, self.audit),
            CalculatorNode(self.llm, CalculatorService()),
            WriterNode(self.llm, AnswerRenderer(self.reports), citations),
            CriticNode(self.llm, ConfidenceScorer()),
            EscalationNode(self.llm, self.escalations, settings.confidence_threshold),
        )
        self.chat = ChatService(
            settings,
            graph,
            self.entitlement,
            self.conversations,
            self.audit,
            AnswerCache(cache_repo),
            self.llm,
            OutputGuard(),
        )

    def startup(self) -> None:
        self.report_admin.cache.clear()
        if self.settings.auto_ingest_on_start and self.store.count() == 0:
            result = self.ingestion.ingest()
            logger.info("auto-ingest finished", extra={"fields": {"reports": result.reports_ingested, "chunks": result.chunks}})
