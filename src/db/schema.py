SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    publisher TEXT NOT NULL,
    published TEXT NOT NULL,
    sector TEXT NOT NULL,
    access TEXT NOT NULL CHECK (access IN ('paid', 'public excerpt'))
);
CREATE TABLE IF NOT EXISTS market_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report TEXT NOT NULL REFERENCES reports(id),
    metric TEXT NOT NULL,
    region TEXT NOT NULL,
    period TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    scope_note TEXT NOT NULL,
    page INTEGER,
    UNIQUE (report, metric, region, period)
);
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    contact_email TEXT NOT NULL,
    purchased_reports TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS escalations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    question TEXT NOT NULL,
    reason TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    payload TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL UNIQUE REFERENCES messages(id),
    rating TEXT NOT NULL CHECK (rating IN ('up', 'down')),
    comment TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS injection_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT,
    kind TEXT NOT NULL,
    source TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    intent TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    latency_ms INTEGER NOT NULL,
    cached INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS answer_cache (
    key TEXT PRIMARY KEY,
    response TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""

SANDBOX_SCHEMA = """
CREATE TABLE reports (id TEXT, title TEXT, publisher TEXT, published TEXT, sector TEXT, access TEXT);
CREATE TABLE market_metrics (report TEXT, metric TEXT, region TEXT, period TEXT, value REAL, unit TEXT, scope_note TEXT, page INTEGER);
"""
