-- sqlfluff:dialect:duckdb
-- Note: indices are created automatically by DuckDB

-- +geese up
CREATE TABLE note (
    sub_dir VARCHAR NOT NULL,
    filename VARCHAR NOT NULL UNIQUE PRIMARY KEY,
    content VARCHAR NOT NULL,
    modified_at TIMESTAMP NOT NULL
);

CREATE TABLE embedding (
    filename VARCHAR NOT NULL,
    embedding VARCHAR NOT NULL,
    FOREIGN KEY (filename) REFERENCES note (filename)
);

-- +geese down
DROP TABLE IF EXISTS embedding;
DROP TABLE IF EXISTS note;
