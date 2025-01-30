-- Docs: https://duckdb.org/docs/sql/statements/overview
CREATE OR REPLACE TABLE users(
    username VARCHAR NOT NULL UNIQUE,
    age INTEGER NOT NULL CHECK (age >= 0) CHECK (height < 150),
    height FLOAT NOT NULL CHECK (height > 0) CHECK (height < 3),
    awesome BOOLEAN NOT NULL,
    bday DATE NOT NULL
);
CREATE UNIQUE INDEX username_index ON users (username);
