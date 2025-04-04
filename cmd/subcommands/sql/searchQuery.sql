-- sqlfluff:dialect:duckdb

SELECT subDir, filename, content, modified_at
FROM note
JOIN embedding USING (filename)
LIMIT ?;
