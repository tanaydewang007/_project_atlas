from src.core.errors import ClientNotFound
from src.models.domain import Report
from src.repositories.clients import ClientRepository
from src.repositories.reports import ReportRepository


class EntitlementService:
    def __init__(self, clients: ClientRepository, reports: ReportRepository) -> None:
        self.clients = clients
        self.reports = reports

    def entitled_ids(self, client_id: str) -> list[str]:
        client = self.clients.get(client_id)
        if client is None:
            raise ClientNotFound(client_id)
        public = [r.id for r in self.reports.all() if r.is_public]
        return sorted(set(client.purchased) | set(public))

    def locked_reports(self, client_id: str) -> list[Report]:
        entitled = set(self.entitled_ids(client_id))
        return [r for r in self.reports.all() if r.id not in entitled]
