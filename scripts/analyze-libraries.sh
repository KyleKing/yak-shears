#!/bin/bash -xe
# Script to analyze latest versions of libraries and optionally update download-assets.sh

# Function to get current version from download-assets.sh
get_current_version() {
	local var=$1
	grep -Eo "$var:-[^}]+" scripts/download-assets.sh | head -1 | cut -d'-' -f2
}

# CodeJar (Git Hash)
CURRENT_CODEJAR=$(get_current_version "CODEJAR_VERSION")
echo -e "\nCurrent CodeJar version: $CURRENT_CODEJAR"

CODEJAR_COMMITS=$(curl -s https://api.github.com/repos/antonmedv/codejar/commits/master)
LATEST_CODEJAR_COMMIT=$(printf "%s" $CODEJAR_COMMITS | jq -r '.sha')
LATEST_CODEJAR_DATE=$(printf "%s" $CODEJAR_COMMITS | jq -r '.commit.committer.date')
echo "Latest CodeJar version: $LATEST_CODEJAR_COMMIT (released $LATEST_CODEJAR_DATE)"

if [ "$CURRENT_CODEJAR" != "$LATEST_CODEJAR_COMMIT" ]; then
	echo "Review changes at: https://github.com/antonmedv/codejar/compare/$CURRENT_CODEJAR...$LATEST_CODEJAR_COMMIT"
else
	echo "No new commits since last version."
fi

# Analyze HTMX (Git Releases)
CURRENT_HTMX=$(get_current_version "HTMX_VERSION")
echo -e "\nCurrent HTMX version: $CURRENT_HTMX"

HTMX_LATEST_RELEASE=$(curl -s https://api.github.com/repos/bigskysoftware/htmx/releases/latest)
LATEST_HTMX_VERSION=$(printf "%s" $HTMX_LATEST_RELEASE | jq -r '.tag_name')
LATEST_HTMX_DATE=$(printf "%s" $HTMX_LATEST_RELEASE | jq -r '.published_at')
echo "Latest HTMX version: $LATEST_HTMX_VERSION (released $LATEST_HTMX_DATE)"

if [ "$CURRENT_HTMX" != "$LATEST_HTMX_VERSION" ]; then
	echo "Changelog for version: https://github.com/bigskysoftware/htmx/releases"
else
	echo "No new releases since last version."
fi

# Conditionally update
# echo -e "\nDo you want to update download-assets.sh with the latest versions? (y/N)"
# read -r response
# if [[ "$response" =~ ^[Yy]$ ]]; then
	sed -i "" "s/$CURRENT_CODEJAR/$LATEST_CODEJAR_COMMIT/" scripts/download-assets.sh
	sed -i "" "s/$CURRENT_HTMX/$LATEST_HTMX_VERSION/" scripts/download-assets.sh
# fi
