-- sqlfluff:dialect:sqlite
-- sqlfluff:templater:placeholder:param_style:question_mark
INSERT INTO geese_migrations (
    migration_id,
    namespace,
    filename,
    migration_up,
    migration_down,
    modified_at
) VALUES (
    ?, ?, ?, ?, ?, ?
)
