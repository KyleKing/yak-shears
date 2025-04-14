package internal_test

import (
	"fmt"
	"strings"
	"testing"

	"github.com/KyleKing/yak-shears/geese-migrations/internal"
)

func TestExtractSQL(t *testing.T) {
	parameters := []struct {
		input, expectedUp, expectedDown string
	}{
		{`
-- +geese up
CREATE TABLE test (id INT);

-- +geese down
DROP TABLE test;
`, "CREATE TABLE test (id INT);", "DROP TABLE test;"},
		{`
-- +geese up
CREATE TABLE test (id INT);
INSERT INTO test (id) VALUES(1), (2);

-- +geese down
`, `CREATE TABLE test (id INT);
INSERT INTO test (id) VALUES(1), (2);`, ""},
	}

	for i, param := range parameters {
		t.Run(fmt.Sprintf("Testing [%v]", i), func(t *testing.T) {
			sqlUp, sqlDown, err := internal.ExtractSQL(param.input)
			if err != nil {
				t.Fatalf("extractSQL failed: %v", err)
			}

			if sqlUp != param.expectedUp {
				t.Logf("incorrect sqlUp returned: %s (expected %s)", sqlUp, param.expectedUp)
			}
			if sqlDown != param.expectedDown {
				t.Logf("incorrect sqlDown returned: %s (expected %s)", sqlDown, param.expectedDown)
			}
			if sqlUp != param.expectedUp || sqlDown != param.expectedDown {
				t.Fail()
			}
		})
	}
}
func TestExtractSQLErrors(t *testing.T) {
	parameters := []struct {
		input, expectedErr string
	}{
		{`
-- +geese up
CREATE TABLE test (id INT);
`, "invalid markers ([1, -1]) in"},
		{`
-- +geese down
`, "invalid markers ([-1, 1]) in"},
	}

	for i, param := range parameters {
		t.Run(fmt.Sprintf("Testing [%v]", i), func(t *testing.T) {
			_, _, err := internal.ExtractSQL(param.input)
			if err == nil {
				t.Fatalf("extractSQL failed to error for: %s", param.input)
			}

			if !strings.Contains(fmt.Sprintf("%v", err), param.expectedErr) {
				t.Fatalf("incorrect err returned: %v (expected %s)", err, param.expectedErr)
			}
		})
	}
}
