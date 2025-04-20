-- sqlfluff:dialect:sqlite
-- sqlfluff:templater:placeholder:param_style:question_mark
SELECT migration_id
FROM geese_migrations
WHERE namespace = ?;
