CREATE TABLE IF NOT EXISTS event_logs (
    log_id UUID PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    session_id UUID NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    search_keyword TEXT,
    item_id VARCHAR(64),
    page_url TEXT
);

CREATE INDEX IF NOT EXISTS idx_event_logs_session_id ON event_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_event_logs_event_type ON event_logs(event_type);
