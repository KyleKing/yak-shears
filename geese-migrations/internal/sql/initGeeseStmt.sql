-- sqlfluff:dialect:sqlite
CREATE TABLE IF NOT EXISTS geese_migrations (
    migration_id INTEGER NOT NULL,
    namespace VARCHAR NOT NULL,
    filename VARCHAR NOT NULL,
    migration_up VARCHAR NOT NULL,
    migration_down VARCHAR NOT NULL,
    modified_at DATE NOT NULL,
    UNIQUE (migration_id, namespace)
);
