-- sqlfluff:dialect:duckdb
-- sqlfluff:templater:placeholder:param_style:colon
SELECT
    note.sub_dir,
    note.filename,
    note.content,
    note.modified_at
FROM note
INNER JOIN embedding ON note.filename = embedding.filename
-- Order by match quality
ORDER BY note.modified_at
LIMIT :limit_ OFFSET :offset_;
