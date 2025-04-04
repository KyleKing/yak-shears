package cmd

import (
	"testing"

	"github.com/stretchr/testify/require"
)

func TestInitCli(t *testing.T) {
	err := InitCli().Run("-help")
	require.NoError(t, err)
}
