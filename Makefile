.PHONY: fetch run build preview clean deploy all

CORPUS_DIR := corpus/files
DATA_DIR   := data
SITE_DIR   := site

all: fetch run build

# Step 1 — download corpus content (idempotent, only fetches missing)
fetch:
	@./scripts/fetch.sh

# Step 2 — run translate over every corpus item, write JSON to data/
run:
	@./scripts/run.sh

# Step 3 — generate static site/index.html from the corpus + translate JSON
build:
	@./scripts/build.sh

# Local preview — open site in browser
preview:
	@open "$(SITE_DIR)/index.html"

# Wipe all generated artifacts
clean:
	rm -rf $(CORPUS_DIR) $(DATA_DIR) $(SITE_DIR)/index.html

# Deploy to Cloudflare Pages
deploy:
	wrangler pages deploy $(SITE_DIR) --project-name=translate-web --commit-dirty=true --branch=master
