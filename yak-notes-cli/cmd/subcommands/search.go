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

	"github.com/KyleKing/yak-shears/yak-notes-cli/cmd/config"
	"github.com/leaanthony/clir"
)

// TODO: implement Ollama client for embeddings
//  https://gobyexample.com/http-client
//  https://www.digitalocean.com/community/tutorials/how-to-make-http-requests-in-go

var (
	//go:embed sql/initStmt.sql
	initStmt string
	//go:embed sql/insertNotesStmt.sql
	insertNotesStmt string
	//go:embed sql/insertEmbeddingsStmt.sql
	insertEmbeddingsStmt string
	//go:embed sql/searchQueryStmt.sql
	searchQueryStmt string
)

type Note struct {
	SubDir     string    `db:"sub_dir"`
	Filename   string    `db:"filename"`
	Content    string    `db:"content"`
	ModifiedAt time.Time `db:"modified_at"`
}

// Batch insert modified notes
func storeNotes(db *sqlx.DB, notes []Note, chunkingFunc func(string) []string) (err error) {
	if len(notes) == 0 {
		return nil
	}
	_, err = db.NamedExec(insertNotesStmt, notes)
	if err != nil {
		return fmt.Errorf("failed to execute batch insertNotes: %w", err)
	}

	// Prepare embeddings for batch insert
	var embeddings []map[string]interface{}
	for _, note := range notes {
		chunks := chunkingFunc(note.Content)
		for _, chunk := range chunks {
			if len(chunk) > 0 {
				embeddings = append(embeddings, map[string]interface{}{
					"filename":  note.Filename,
					"embedding": chunk,
				})
			}
		}
	}

	// Batch insert embeddings
	if len(embeddings) > 0 {
		_, err = db.NamedExec(insertEmbeddingsStmt, embeddings)
		if err != nil {
			return fmt.Errorf("failed to execute batch insertEmbeddings: %w", err)
		}
	}
	return nil
}

// Default chunking logic: split by paragraph, then by sentence if necessary
func defaultChunkingLogic(content string) []string {
	var chunks []string
	paragraphs := strings.Split(content, "\n\n")
	for _, paragraph := range paragraphs {
		if len(paragraph) > 500 { // Example threshold for large chunks
			sentences := strings.Split(paragraph, ". ")
			chunks = append(chunks, sentences...)
		} else {
			chunks = append(chunks, paragraph)
		}
	}
	return chunks
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

	if err := storeNotes(db, notes, defaultChunkingLogic); err != nil {
		return fmt.Errorf("failed to store notes for subdir %s: %w", subDir, err)
	}
	return nil
}

// Purge data
func purgeData(db *sqlx.DB) (err error) {
	// PLANNED: DROP IF EXISTS _ CASCADE should require only dropping the note table, right?
	_, err = db.Exec("DELETE FROM embedding")
	if err != nil {
		return fmt.Errorf("failed to purge embedding table: %w", err)
	}
	_, err = db.Exec("DELETE FROM note")
	if err != nil {
		return fmt.Errorf("failed to purge note table: %w", err)
	}
	return nil
}

// Ingest ALL Notes
func ingestAllNotes(db *sqlx.DB, syncDir string) (err error) {
	if err = purgeData(db); err != nil {
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

	_, err = db.Exec(initStmt)
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
		if err := os.Remove(filepath.Join(syncDir, "yak-shears.db")); err != nil && !os.IsNotExist(err) {
			return fmt.Errorf("failed to remove database file: %w", err)
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
