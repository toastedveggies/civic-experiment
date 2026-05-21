CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    government_level TEXT NOT NULL,
    body_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    collection_method TEXT NOT NULL,
    base_url TEXT,
    meeting_frequency TEXT,
    priority_level TEXT NOT NULL,
    status TEXT NOT NULL,
    adapter TEXT,
    parser TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    external_id TEXT,
    title TEXT,
    document_type TEXT,
    meeting_date TEXT,
    body_name TEXT,
    jurisdiction TEXT,
    file_path TEXT,
    text_path TEXT,
    ocr_text_path TEXT,
    sha256 TEXT,
    mime_type TEXT,
    page_count INTEGER,
    parent_document_id TEXT,
    collected_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(source_id),
    FOREIGN KEY (parent_document_id) REFERENCES documents(document_id)
);

CREATE TABLE IF NOT EXISTS agenda_items (
    agenda_item_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    meeting_date TEXT,
    item_number TEXT,
    item_title TEXT,
    department TEXT,
    sponsor TEXT,
    action_type TEXT,
    funding_amount TEXT,
    funding_source TEXT,
    deadlines TEXT,
    affected_populations TEXT,
    geography TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(document_id)
);

CREATE TABLE IF NOT EXISTS findings (
    finding_id TEXT PRIMARY KEY,
    agenda_item_id TEXT,
    document_id TEXT NOT NULL,
    summary_plain TEXT NOT NULL,
    why_it_matters TEXT,
    priority_level TEXT,
    trend_signal TEXT,
    action_classification TEXT,
    ambiguity_note TEXT,
    memory_status TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agenda_item_id) REFERENCES agenda_items(agenda_item_id),
    FOREIGN KEY (document_id) REFERENCES documents(document_id)
);

CREATE TABLE IF NOT EXISTS finding_topics (
    finding_id TEXT NOT NULL,
    topic_slug TEXT NOT NULL,
    PRIMARY KEY (finding_id, topic_slug),
    FOREIGN KEY (finding_id) REFERENCES findings(finding_id)
);

CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    agenda_item_id TEXT,
    excerpt_text TEXT,
    page_reference TEXT,
    section_reference TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (finding_id) REFERENCES findings(finding_id),
    FOREIGN KEY (document_id) REFERENCES documents(document_id),
    FOREIGN KEY (agenda_item_id) REFERENCES agenda_items(agenda_item_id)
);

CREATE TABLE IF NOT EXISTS trendlines (
    trendline_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    first_seen_date TEXT,
    last_seen_date TEXT,
    current_assessment TEXT,
    key_actors TEXT,
    representative_items TEXT,
    what_to_watch_next TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trendline_findings (
    trendline_id TEXT NOT NULL,
    finding_id TEXT NOT NULL,
    relationship_type TEXT,
    PRIMARY KEY (trendline_id, finding_id),
    FOREIGN KEY (trendline_id) REFERENCES trendlines(trendline_id),
    FOREIGN KEY (finding_id) REFERENCES findings(finding_id)
);

CREATE INDEX IF NOT EXISTS idx_documents_source_id ON documents(source_id);
CREATE INDEX IF NOT EXISTS idx_documents_meeting_date ON documents(meeting_date);
CREATE INDEX IF NOT EXISTS idx_agenda_items_document_id ON agenda_items(document_id);
CREATE INDEX IF NOT EXISTS idx_findings_document_id ON findings(document_id);
CREATE INDEX IF NOT EXISTS idx_findings_agenda_item_id ON findings(agenda_item_id);
