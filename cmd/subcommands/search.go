package subcommands

import (
	_ "embed" // Required for compiler
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/jmoiron/sqlx"
	_ "github.com/marcboeker/go-duckdb" // Configure DuckDB driver

	"github.com/KyleKing/yak-shears/cmd/config"
	"github.com/leaanthony/clir"
)

// TODO: implement Ollama client for embeddings
//  https://gobyexample.com/http-client
//  https://www.digitalocean.com/community/tutorials/how-to-make-http-requests-in-go

var (
	//go:embed sql/init.sql
	sqlInitStmt string
	//go:embed sql/insertNote.sql
	insertNoteStmt string
	//go:embed sql/insertEmbedding.sql
	insertEmbeddingStmt string
	//go:embed sql/searchQuery.sql
	searchQueryStmt string
)

type Note struct {
	SubDir     string    `db:"sub_dir"`
	Filename   string    `db:"filename"`
	Content    string    `db:"content"`
	ModifiedAt time.Time `db:"modified_at"`
}

// Upsert modified notes
func storeNotes(db *sqlx.DB, notes []Note) (err error) {
	// PLANNED: submit multiple notes in single statement
	for _, note := range notes {
		_, err := db.NamedExec(insertNoteStmt, note)
		if err != nil {
			return fmt.Errorf("failed to execute insertNote for note %s: %w", note.Filename, err)
		}

		// TODO: Consider alternative chunking techniques
		for _, chunk := range strings.Split(note.Content, `\n`) {
			_, err := db.NamedExec(insertEmbeddingStmt, map[string]interface{}{
				"filename":  note.Filename,
				"embedding": chunk,
			})
			if err != nil {
				return fmt.Errorf("failed to execute insertEmbeddingStmt for chunk in note %s: %w", note.Filename, err)
			}
		}
	}
	return
}

func ingestSubdir(db *sqlx.DB, syncDir, subDir string) (err error) {
	dir := filepath.Join(syncDir, subDir)
	files, err := os.ReadDir(dir)
	if err != nil {
		return fmt.Errorf("failed to read directory %s: %w", dir, err)
	}

	notes := []Note{}
	for _, file := range files {
		if !file.IsDir() && strings.HasSuffix(file.Name(), ".dj") {
			fi, err := file.Info()
			if err != nil {
				return fmt.Errorf("failed to get file info for %s: %w", file.Name(), err)
			}
			content, err := os.ReadFile(filepath.Join(dir, file.Name()))
			if err != nil {
				return fmt.Errorf("failed to read file %s: %w", file.Name(), err)
			}
			note := Note{SubDir: subDir, Filename: file.Name(), Content: string(content), ModifiedAt: fi.ModTime()}
			notes = append(notes, note)
		}
	}

	if err := storeNotes(db, notes); err != nil {
		return fmt.Errorf("failed to store notes for subdir %s: %w", subDir, err)
	}
	return nil
}

// Purge data
func dropDataHack(db *sqlx.DB) (err error) {
	_, err = db.Exec("DROP TABLE IF EXISTS note CASCADE")
	if err != nil {
		return fmt.Errorf("failed to remove tables: %w", err)
	}
	return nil
}

// Ingest ALL Notes
func ingestAllNotes(db *sqlx.DB, syncDir string) (err error) {
	if err = dropDataHack(db); err != nil {
		return err
	}

	folderNames, err := ListsubDirs(syncDir)
	if err != nil {
		return fmt.Errorf("failed to list subdirectories in %s: %w", syncDir, err)
	}
	for _, subDir := range folderNames {
		err := ingestSubdir(db, syncDir, subDir)
		if err != nil {
			return fmt.Errorf("failed to ingest subdir %s: %w", subDir, err)
		}
	}
	return nil
}

// Search for note in database (TODO: currently only a PoC without WHERE/'query')
func search(db *sqlx.DB, query string) (err error) {
	fmt.Printf("Warning: does not yet use query='%s'", query)
	notes := []Note{}
	nstmt, err := db.PrepareNamed(searchQueryStmt)
	if err != nil {
		return fmt.Errorf("failed to prepare search query: %w", err)
	}
	defer nstmt.Close()
	err = nstmt.Select(&notes, map[string]interface{}{
		"limit_":  2,
		"offset_": 0,
	})
	if err != nil {
		return fmt.Errorf("failed to execute search query: %w", err)
	}

	log.Println("\n\n==============\n ")
	for _, n := range notes {
		log.Printf("\n\n--------------\n\n%s | %s | %v\n%s", n.SubDir, n.Filename, n.ModifiedAt.Format(time.RFC3339), n.Content)
	}
	log.Println("\n\n==============\n ")
	return nil
}

// Connect to the database and non-destructively initialize the schema, if not already found
func connectDB(dir string) (db *sqlx.DB, err error) {
	path := filepath.Join(dir, "yak-shears.db?access_mode=READ_WRITE")
	db, err = sqlx.Open("duckdb", path)
	if err != nil {
		return nil, fmt.Errorf("failed to open database at %s: %w", path, err)
	}

	// PLANNED: use a connection for threading
	// conn, err := db.Conn(context.Background())
	// defer conn.Close()
	// return conn, nil

	_, err = db.Exec(sqlInitStmt)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize database schema: %w", err)
	}
	return db, nil
}

// CLI

type SearchQuery struct {
	Query string `description:"" pos:"1"`
}

func AttachSearch(cli *clir.Cli) {
	searchCmd := cli.NewSubCommand("search", "Search notes")

	searchQuery := SearchQuery{}
	searchCmd.AddFlags(&searchQuery)

	syncDir := config.GetSyncDir()
	searchCmd.StringFlag("sync-dir", "Sync Directory", &syncDir)

	searchCmd.Action(func() (err error) {
		// HACK: if the schema changes, the current workaround is to remove the file
		if err := os.Remove(filepath.Join(syncDir, "yak-shears.db")); err != nil {
			return err
		}

		db, err := connectDB(syncDir)
		if err != nil {
			return err
		}
		defer db.Close()

		// HACK: replace with conditional and incremental ingestion
		if err := ingestAllNotes(db, syncDir); err != nil {
			return err
		}
		if err := search(db, searchQuery.Query); err != nil {
			return err
		}
		return
	})
}
