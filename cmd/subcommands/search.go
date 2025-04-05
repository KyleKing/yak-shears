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
	_ "github.com/marcboeker/go-duckdb"

	"github.com/KyleKing/yak-shears/cmd/config"
	"github.com/leaanthony/clir"
)

// TODO: implement Ollama client for embeddings
//  https://gobyexample.com/http-client
//  https://www.digitalocean.com/community/tutorials/how-to-make-http-requests-in-go

//go:embed sql/init.sql
var SQL_INIT string

//go:embed sql/insertNote.sql
var INSERT_NOTE string

//go:embed sql/insertEmbedding.sql
var INSERT_EMBEDDING string

//go:embed sql/searchQuery.sql
var SEARCH_QUERY string

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
		_, err := db.NamedExec(INSERT_NOTE, note)
		if err != nil {
			return fmt.Errorf("failed to execute INSERT_NOTE for note %s: %w", note.Filename, err)
		}

		for _, chunk := range strings.Split(note.Content, `\n`) {
			_, err := db.NamedExec(INSERT_EMBEDDING, map[string]interface{}{
				"filename":  note.Filename,
				"embedding": chunk,
			})
			if err != nil {
				return fmt.Errorf("failed to execute INSERT_EMBEDDING for chunk in note %s: %w", note.Filename, err)
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

// Ingest ALL Notes
func ingestAllNotes(db *sqlx.DB, syncDir string) (err error) {
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

// Remove ALL notes
func removeAllNotes(db *sqlx.DB) {
	_, err := db.Exec("DELETE FROM embedding")
	check(err)
	_, err = db.Exec("DELETE FROM note")
	check(err)
}

// Search for note in database
func search(db *sqlx.DB, query string) (err error) {
	notes := []Note{}
	err = db.Select(&notes, SEARCH_QUERY, map[string]interface{}{
		"limit_":  2,
		"offset_": 0,
	})
	if err != nil {
		return fmt.Errorf("failed to execute search query: %w", err)
	}

	for _, n := range notes {
		log.Printf("%s | %s | %v\n%s", n.SubDir, n.Filename, n.ModifiedAt.Format(time.RFC3339), n.Content)
	}
	return nil
}

// Connect to the database and non-destructively initialize the schema, if not already found
func connectDb(dir string) (db *sqlx.DB, err error) {
	path := filepath.Join(dir, "yak-shears.db?access_mode=READ_WRITE")
	db, err = sqlx.Open("duckdb", path)
	if err != nil {
		return nil, fmt.Errorf("failed to open database at %s: %w", path, err)
	}

	// PLANNED: use a connection for threading
	// conn, err := db.Conn(context.Background())
	// check(err)
	// defer conn.Close()
	// return conn, nil

	_, err = db.Exec(SQL_INIT)
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

		db, err := connectDb(syncDir)
		if err != nil {
			return err
		}
		defer db.Close()
		// // HACK: removal and re-ingestion is sub-optimal and only for development
		// removeAllNotes(db)
		if err := ingestAllNotes(db, syncDir); err != nil {
			return err
		}
		if err := search(db, searchQuery.Query); err != nil {
			return err
		}
		return
	})
}
