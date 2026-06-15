-- Harness v0 schema - migration 003
-- Tool registry for discoverable local capabilities.

CREATE TABLE IF NOT EXISTS tool (
    name           TEXT PRIMARY KEY,
    provider       TEXT NOT NULL DEFAULT 'project',
    command        TEXT NOT NULL,
    description    TEXT NOT NULL,
    args           TEXT,
    responsibility TEXT NOT NULL,
    since          TEXT NOT NULL DEFAULT (datetime('now')),
    kind           TEXT NOT NULL DEFAULT 'cli'
                   CHECK(kind IN ('cli','binary','mcp','skill','http')),
    capability     TEXT,
    scan_target    TEXT,
    status         TEXT NOT NULL DEFAULT 'unknown'
                   CHECK(status IN ('present','missing','unknown')),
    checked_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_tool_capability ON tool(capability);
CREATE INDEX IF NOT EXISTS idx_tool_status ON tool(status);
CREATE INDEX IF NOT EXISTS idx_tool_responsibility ON tool(responsibility);

INSERT OR IGNORE INTO schema_version (version) VALUES (3);
