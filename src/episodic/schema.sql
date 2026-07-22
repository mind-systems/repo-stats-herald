CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS episodic_entries (
    id bigserial PRIMARY KEY,
    repo text NOT NULL,
    org_id bigint NOT NULL,
    completed_tasks text[] NOT NULL,
    commit_shas text[] NOT NULL,
    content text NOT NULL,
    embedding vector(768) NOT NULL,
    changed_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS episodic_entries_embedding_cos_idx ON episodic_entries USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS episodic_entries_repo_changed_at_idx ON episodic_entries (repo, changed_at);
