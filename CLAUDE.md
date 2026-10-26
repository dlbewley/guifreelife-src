# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Hugo source for the personal technical blog https://guifreelife.com (Dale Bewley): OpenShift, Kubernetes, networking, Linux. Almost all content is Markdown blog posts in `content/blog/`.

## Commands

- `make preview` (`hugo server -D`): local dev server, drafts included.
- `hugo --minify`: production build into `public/` (gitignored). CI uses **Hugo extended 0.164.0**, so match that version. `asciidoctor` is also installed in CI for `.adoc` content, though there is currently none.
- `make stingers`: regenerates the YouTube intro/outro videos (`dev/stingers/make_stinger.py`, needs `ffmpeg` and Pillow) and copies them to `static/videos/`. See `dev/stingers/README.md`.
- `make banners` / `thumbnails` / `photogrid`: ImageMagick image pipelines. The `bin/*.sh` scripts have hardcoded macOS paths (`/Users/dale/...`) and use `gsed`, so treat them as legacy one-offs.

There are no tests. `.prettierrc.json` and `.stylelintrc.json` exist; the theme's `package.json` has `stylelint`/`prettier`/`eslint` scripts, but nothing runs them in CI.

## Deployment

Pushing to `master` triggers `.github/workflows/gh-pages.yml`, which builds the site and publishes `public/` to a **different repo**, `dlbewley/dlbewley.github.io` (branch `master`, CNAME `guifreelife.com`), using a deploy key. A merge to `master` goes live.

## Structure

- **Theme**: `themes/hugo-universal-theme` is **vendored and committed** (not a submodule) and has been modified in place: it adds the shortcodes `collapsable`, `asciinema`, `credly` and `img`, plus Mermaid support (`partials/mermaid.html`, `_default/_markup/render-codeblock-mermaid.html`). Site-level overrides in the top-level `layouts/` take precedence over the theme: `share-buttons.html`, `carousel.html`, and the shortcodes `gist`, `video` and `clearfix`.
- `gist` is a local replacement for Hugo's built-in gist shortcode, which was removed in Hugo v0.156.0.
- `data/carousel/*.yaml` and `data/features/*.yaml` drive the homepage widgets (enabled in `config.toml` `[params.*]`). `data/testimonials` and `data/clients` are disabled.
- Static assets: post images go in `static/images/`, random post banners in `static/img/banners/banner-N.jpg`, asciinema recordings in `static/casts/<key>.cast`, videos in `static/videos/`.

## Blog post conventions

Front matter, as used by current posts (the theme archetype sets `layout: post`, `draft: true` and the `draft` tag):

```yaml
---
title: "..."
date: 2026-02-18
layout: post
banner: /images/foo.png     # hero image + og:image; falls back to img/sharing-default.png
mermaid: true               # REQUIRED to load mermaid JS for ```mermaid code blocks
asciinema: true             # REQUIRED to load the player for {{< asciinema >}}
tags: [openshift, kubernetes]
description: One-line summary used for SEO/sharing.
---
```

- The permalink is `/blog/:year/:month/:day/:contentbasename/`, so the filename (e.g. `OVN-Recon-Making-OpenShift-Networking-Connections.md`) becomes the URL slug. `disablePathToLower = true` keeps its case.
- Put `<!--more-->` after the intro paragraph to set the summary cutoff.
- Posts mostly use reference-style links (`[text][ref]` with `[ref]: url` definitions at the bottom). Internal links use `{{< ref "/blog/Some-Post.md" >}}`.
- `{{< asciinema key="name" rows="50" ... >}}` loads `/casts/name.cast`.
- `{{< collapsable prompt="..." collapse=true md=true >}}...{{< /collapsable >}}`: with `md=true`, `markdownify` only sees link definitions *inside* the shortcode body, so reference-link definitions have to be duplicated inside the block. Use `{{< >}}` delimiters, not `{{% %}}`; Goldmark re-parses `%` output and breaks the toggle HTML. Goldmark `unsafe` rendering is off.

## Secrets scanning

`.gitleaks.toml` allowlists the Google Maps API key in `config.toml`, which is intentionally public, and two older posts containing example credentials. Update the allowlist if you add similar intentional matches.
