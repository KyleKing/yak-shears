package cmd_test

import (
	"testing"

	"github.com/KyleKing/yak-shears/cmd"
	"github.com/stretchr/testify/require"
)

func TestInitCli(t *testing.T) {
	err := cmd.InitCli().Run("-help")
	require.NoError(t, err)
}
