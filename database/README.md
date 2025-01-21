# Database

- Prefer [native database libraries rather than an abstract interface](https://crawshaw.io/blog/go-and-sqlite) when working with SQLite for better errors and additional features
    - Use [github.com/zombiezen/go-sqlite](https://github.com/zombiezen/go-sqlite) for `sqlite`
        - Alternatively, [this](https://earthly.dev/blog/golang-sqlite) is likely the most popular SQLite module built on the generic interface
    - But [use DuckDB's official client](https://github.com/marcboeker/go-duckdb), which is based on the generic interface
- Consider using [go:embed](https://pkg.go.dev/embed) for SQL
