CREATE TABLE IF NOT EXISTS served_repos (
    org_id bigint NOT NULL,
    repo   text   NOT NULL,
    PRIMARY KEY (org_id, repo)
);
