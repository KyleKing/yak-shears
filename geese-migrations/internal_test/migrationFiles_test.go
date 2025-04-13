package internal_test

import (
	"testing"

	"github.com/KyleKing/yak-shears/geese-migrations/internal"
)

func TestExtractSQL(t *testing.T) {
	content := `
-- +geese up
CREATE TABLE test (id INT);

-- +geese down
DROP TABLE test;
`

	expectedUp := "CREATE TABLE test (id INT);"
	expectedDown := "DROP TABLE test;"
	sqlUp, sqlDown, err := internal.ExtractSQL(content)
	if err != nil {
		t.Fatalf("extractSQL failed: %v", err)
	}

	if sqlUp != expectedUp {
		t.Errorf("incorrect sqlUp returned: %s (expected %s)", sqlUp, expectedUp)
	}
	if sqlDown != expectedDown {
		t.Errorf("incorrect sqlDown returned: %s (expected %s)", sqlDown, expectedDown)
	}
}
