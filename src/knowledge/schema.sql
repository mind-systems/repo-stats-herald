CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    repo text NOT NULL,
    path text NOT NULL,
    chunk_index int NOT NULL,
    content text NOT NULL,
    embedding vector(768) NOT NULL,
    PRIMARY KEY (repo, path, chunk_index)
);

CREATE INDEX IF NOT EXISTS chunks_embedding_cos_idx ON chunks USING hnsw (embedding vector_cosine_ops);
