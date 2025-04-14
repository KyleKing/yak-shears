-- sqlfluff:dialect:duckdb
-- +geese up
CREATE TABLE note (
    sub_dir VARCHAR NOT NULL,
    filename VARCHAR NOT NULL UNIQUE PRIMARY KEY,
    content VARCHAR NOT NULL,
    modified_at DATE NOT NULL
);
-- +geese down
DROP TABLE IF EXISTS note;
