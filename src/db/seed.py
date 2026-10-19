from src.db.database import Database

REPORTS = [
    ("R-101", "Global Smart Water Meter Market 2025", "CMR", "2025-03-10", "Utilities", "paid"),
    ("R-102", "Smart Water Metering: Industry Outlook 2024", "Aquila Insights (third party)", "2024-06-18", "Utilities", "public excerpt"),
    ("R-103", "Residential Water Purifier Market 2025", "CMR", "2025-01-22", "Consumer Durables", "paid"),
    ("R-104", "Global Industrial IoT Sensors Market 2025", "CMR", "2025-02-11", "Industrial", "paid"),
    ("R-105", "Electric Vehicle Charging Infrastructure Market 2025", "CMR", "2025-04-02", "Automotive", "paid"),
    ("R-106", "Cloud Cybersecurity Services Market 2024", "CMR", "2024-11-20", "Technology", "paid"),
]

METRICS = [
    ("R-101", "Market size", "Global", "2024", 4.21, "USD B", "Includes hardware, software and services", 8),
    ("R-101", "CAGR", "Global", "2025-2030", 11.2, "%", "Forecast period stated as 2025-2030", 8),
    ("R-101", "Regional share", "APAC", "2024", 38.0, "%", "Share of global market size", 8),
    ("R-102", "Market size", "Global", "2024", 3.87, "USD B", "AMR / AMI hardware only", 5),
    ("R-102", "CAGR", "Global", "2024-2029", 9.8, "%", "Different forecast window from R-101", 5),
    ("R-102", "Regional share", "APAC", "2024", 41.0, "%", "Share of hardware market", 9),
    ("R-103", "Market size", "Global", "2024", 38.6, "USD B", "Household water purifiers including consumables", 4),
    ("R-103", "CAGR", "Global", "2025-2030", 7.4, "%", "Forecast period stated as 2025-2030", 4),
    ("R-103", "Regional share", "APAC", "2024", 46.0, "%", "Share of global market size", 4),
    ("R-104", "Market size", "Global", "2024", 18.9, "USD B", "Sensor hardware and embedded firmware", 3),
    ("R-104", "CAGR", "Global", "2025-2030", 9.1, "%", "Forecast period stated as 2025-2030", 3),
    ("R-104", "Regional share", "APAC", "2024", 35.0, "%", "Share of global market size", 3),
    ("R-105", "Market size", "Global", "2024", 31.4, "USD B", "Chargers, installation and network software", 3),
    ("R-105", "CAGR", "Global", "2025-2030", 22.5, "%", "Forecast period stated as 2025-2030", 3),
    ("R-105", "Regional share", "APAC", "2024", 52.0, "%", "Share of global market size", 3),
    ("R-106", "Market size", "Global", "2024", 72.3, "USD B", "Managed and professional cloud security services", 3),
    ("R-106", "CAGR", "Global", "2025-2030", 12.8, "%", "Forecast period stated as 2025-2030", 3),
    ("R-106", "Regional share", "APAC", "2024", 24.0, "%", "Share of global market size", 3),
]

CLIENTS = [
    ("C-01", "Northwind Utilities", "ops@example.com", "R-101, R-103"),
    ("C-02", "Blue Delta Infra", "procurement@example.com", "R-103"),
]


class Seeder:
    def __init__(self, db: Database) -> None:
        self.db = db

    def run(self) -> None:
        with self.db.connect() as conn:
            if conn.execute("PRAGMA user_version").fetchone()[0] >= 1:
                return
            conn.executemany("INSERT OR IGNORE INTO reports VALUES (?,?,?,?,?,?)", REPORTS)
            conn.executemany(
                "INSERT OR IGNORE INTO market_metrics (report, metric, region, period, value, unit, scope_note, page) VALUES (?,?,?,?,?,?,?,?)",
                METRICS,
            )
            conn.executemany("INSERT OR IGNORE INTO clients VALUES (?,?,?,?)", CLIENTS)
            conn.execute("PRAGMA user_version = 1")
