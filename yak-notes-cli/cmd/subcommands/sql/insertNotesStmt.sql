-- sqlfluff:dialect:duckdb
-- sqlfluff:templater:placeholder:param_style:colon
INSERT INTO note (sub_dir, filename, content, modified_at) VALUES (
    :sub_dir, :filename, :content, :modified_at
)
