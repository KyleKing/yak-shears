-- Docs: https://duckdb.org/docs/sql/statements/overview
CREATE TABLE IF NOT EXISTS note(
    subfolder VARCHAR NOT NULL,
    filename VARCHAR NOT NULL UNIQUE,
    content VARCHAR NOT NULL,
    modified_at DATE NOT NULL
);

DROP INDEX IF EXISTS filename_index;
CREATE UNIQUE INDEX filename_index ON note (filename);
