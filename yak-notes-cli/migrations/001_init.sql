-- sqlfluff:dialect:duckdb
-- Note: indices are created automatically by DuckDB

-- +geese up
CREATE TABLE IF NOT EXISTS note (
    sub_dir VARCHAR NOT NULL,
    filename VARCHAR NOT NULL UNIQUE PRIMARY KEY,
    content VARCHAR NOT NULL,
    modified_at DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS embedding (
    filename VARCHAR NOT NULL,
    embedding VARCHAR NOT NULL,
    FOREIGN KEY (filename) REFERENCES note (filename)
);

-- +geese down
DROP TABLE IF EXISTS embedding;
DROP TABLE IF EXISTS note;
