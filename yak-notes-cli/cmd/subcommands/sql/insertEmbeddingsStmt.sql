-- sqlfluff:dialect:duckdb
-- sqlfluff:templater:placeholder:param_style:colon
INSERT INTO embedding (filename, embedding) VALUES (:filename, :embedding)
