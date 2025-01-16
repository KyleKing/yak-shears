package cmd

import (
	"testing"

	"github.com/stretchr/testify/require"
)

func TestMain(t *testing.T) {
	// How to test stdout?

	err := Main().Run("-help")
	require.NoError(t, err)

	err = Main().Run("create", "--name", "bob", "--age", "30")
	require.NoError(t, err)

	err = Main().Run("-awesome")
	require.NoError(t, err)

}
