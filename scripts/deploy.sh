#!/usr/bin/env bash
# Build the VitePress site and publish it to the gh-pages branch of luxiang0412/letta-memory-book.
# Pages then serves https://luxiang0412.github.io/letta-memory-book/ (enable once: repo Settings → Pages →
# Deploy from branch → gh-pages / root; the first push of gh-pages usually enables it automatically).
# Works without the `workflow` token scope (no GitHub Actions involved).
set -euo pipefail
cd "$(dirname "$0")/.."
npm run build
cd .vitepress/dist
touch .nojekyll                      # keep files/folders starting with "_"
git init -q -b gh-pages
git add -A
git -c user.name="$(git config --global user.name)" -c user.email="$(git config --global user.email)" \
    commit -qm "deploy: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git push -f git@github.com:luxiang0412/letta-memory-book.git gh-pages
rm -rf .git
