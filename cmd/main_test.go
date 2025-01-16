package cmd

import (
	"testing"

	"github.com/stretchr/testify/require"
)

func TestMain(t *testing.T) {
	err := Main().Run("-help")
	require.NoError(t, err)
}
