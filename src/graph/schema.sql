CREATE TABLE IF NOT EXISTS project_edges (
    from_repo text NOT NULL,
    to_repo text NOT NULL,
    kind text NOT NULL,
    source text NOT NULL,
    PRIMARY KEY (from_repo, to_repo, kind)
);
