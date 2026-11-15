CREATE TABLE links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    short_code  TEXT    NOT NULL,
    target_url  TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    expires_at  TEXT,
    disabled    INTEGER NOT NULL DEFAULT 0 CHECK (disabled IN (0, 1))
);

CREATE UNIQUE INDEX idx_links_short_code ON links (short_code);
