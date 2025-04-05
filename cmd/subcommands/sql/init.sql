CREATE TABLE IF NOT EXISTS note (
    sub_dir VARCHAR NOT NULL,
    filename VARCHAR NOT NULL UNIQUE PRIMARY KEY,
    content VARCHAR NOT NULL,
    modified_at DATE NOT NULL
);

DROP INDEX IF EXISTS filename_index;
CREATE UNIQUE INDEX filename_index ON note (filename);

CREATE TABLE IF NOT EXISTS embedding (
    filename VARCHAR NOT NULL,
    embedding VARCHAR NOT NULL,
    FOREIGN KEY (filename) REFERENCES note (filename)
);
