# Repository Guidelines

## Project Structure & Module Organization
This repository is a Hugo site for the Chinese translation of *Designing Data-Intensive Applications*. Main content lives under `content/`: `content/zh` for the current Simplified Chinese edition, `content/tw` for Traditional Chinese, and `content/v1` / `content/v1_tw` for the first edition. Site configuration is in `hugo.yaml`, translation metadata in `metadata.yaml` and `i18n/*.yaml`, reusable templates in `layouts/shortcodes/`, styles in `assets/css/`, and images in `static/`.

Utility scripts live in `bin/`. Use `bin/zh-tw.py` to regenerate Traditional Chinese content and `bin/epub` / `bin/preprocess-epub.py` for EPUB export.

## Build, Test, and Development Commands
- `make dev`: start the local Hugo server for preview.
- `make build`: build the production site into `public/`.
- `make translate`: regenerate `content/tw` and `content/v1_tw` from Simplified Chinese sources.
- `make epub`: export EPUB artifacts with the repository scripts.
- `hugo --gc --minify`: match the GitHub Pages build more closely when you want a release-style local check.

## Coding Style & Naming Conventions
Prefer small, focused edits. Markdown chapters use lowercase, hyphenated filenames such as `part-ii.md`; chapter files follow `ch<number>.md`. Keep heading structure stable so Hugo ToC, anchors, and cross-links do not drift.

For Python scripts in `bin/`, follow existing style: 4-space indentation, standard library imports first, and simple CLI-oriented functions. Preserve UTF-8 text handling and do not rename generated content directories without updating `hugo.yaml`.

## Testing Guidelines
There is no dedicated automated test suite in this repository. Treat build validation as the minimum check:
- run `make build` after content, config, shortcode, or asset changes;
- run `make translate` when editing Simplified Chinese source that should sync to `tw` or `v1_tw`;
- verify changed pages locally with `make dev`, especially links, footnotes, figures, and chapter navigation.

## Commit & Pull Request Guidelines
Recent history uses short imperative subjects, often with Conventional Commit prefixes such as `fix(epub): ...`, `feat(epub): ...`, or concise Chinese summaries like `更新贡献者列表`. Follow that pattern and keep one logical change per commit.

PRs should state scope, affected paths, and verification commands. Link related issues when applicable. Include screenshots only for visible site or layout changes; text-only translation fixes usually do not need them.
