# translate-web

Showcase site for [translate](https://github.com/Arthur-Ficial/translate) — Apple's Translation framework as a UNIX CLI. Mobile-first landing page with an auto-generated public-domain test corpus, served at https://translate.franzai.com.

The corpus, the translate output, and the rendered showcase cards are all generated from a real `translate` binary at build time. Nothing is mocked.

## Layout

```
corpus/manifest.json     declarative list of test items (CC0 / Public Domain only)
corpus/files/            fetched source documents (gitignored)
data/                    translate's JSON output, one file per corpus item (gitignored)
scripts/fetch.sh         resolves Wikimedia API URLs and downloads
scripts/run.sh           runs the real translate binary against every item
scripts/build.sh         concatenates header + auto-generated cards + footer into site/index.html
site/templates/header.html, footer.html
site/index.html          generated at build time -- single file, all CSS/JS inline
```

## Build

```sh
make all                 # fetch + run + build
make preview             # open the generated site locally
make deploy              # push to Cloudflare Pages (wrangler must be authed)
```

`make run` requires `translate` on PATH (`brew install Arthur-Ficial/tap/translate`).

## Why the build is also a battle test

Every showcase card is generated from a real translate invocation. If the binary breaks, the build fails. The site is a continuous integration check for the whole apfel ecosystem's translation surface.

## License

Site code: MIT. Corpus content: CC0 / Public Domain (every item declares its source on Wikimedia Commons).
