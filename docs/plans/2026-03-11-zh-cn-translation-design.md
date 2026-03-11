# content/en -> content/zh-cn Translation Design

## Goal

Translate every Markdown file in `content/en/` into Simplified Chinese and write the output to `content/zh-cn/`, without reading from or reusing `content/zh/`.

## Scope

- Source of truth is `content/en/*.md`.
- Output directory is `content/zh-cn/`.
- Existing `content/zh-cn/` content is discarded and rebuilt.
- Translation style is faithful to the English source, with moderate smoothing for natural Simplified Chinese.
- Only chapter-like internal links are rewritten to `/zh-cn/...`.
- Image paths, static asset paths, code blocks, anchors, URLs, and front matter structure remain intact.

## Constraints

- Do not use `content/zh/` as translation input, reference text, or fallback.
- Preserve Markdown semantics, including:
  - YAML front matter
  - heading levels
  - footnotes
  - tables
  - blockquotes
  - fenced code blocks
  - raw HTML such as `<a id="..."></a>`
- Keep file names identical to the English source tree.
- Keep output reproducible so the workflow can be rerun safely.

## Recommended Approach

Use a scripted pipeline that processes files one by one:

1. Enumerate `content/en/*.md`.
2. Remove and recreate `content/zh-cn/`.
3. For each file:
   - split front matter from body
   - translate only natural-language Markdown content
   - preserve formatting-sensitive regions
   - rewrite chapter-like internal links from `/ch1`, `/part-i`, `/preface`, `/toc`, etc. to `/zh-cn/...`
4. Run structural checks on each generated file.
5. Run repository-level verification on file counts and link patterns.

This approach is preferred because it is restartable, auditable, and less error-prone than manual one-shot translation of a 260k-word corpus.

## Translation Rules

### Must preserve verbatim

- YAML keys and delimiters
- code fences and inline code
- file paths, command lines, URLs
- footnote markers such as `[^1]`
- explicit anchors and HTML tags
- image and asset paths

### May be translated

- prose paragraphs
- headings
- quote text
- admonition text such as `[!TIP]` bodies

### Terminology policy

- Prefer stable Chinese renderings with English retained at first mention where helpful.
- Keep names of people, products, standards, and libraries in their standard form.
- Enforce consistent terminology across all chapters.

## Validation

For each generated file, verify:

- front matter is still parseable
- heading hierarchy is unchanged
- footnotes still match references
- fenced code blocks are unmodified
- rewritten internal links point to `/zh-cn/...`

Repository-wide verification should include:

- file count in `content/zh-cn/` matches `content/en/`
- no missing or extra Markdown files
- no residual chapter-style links pointing to root paths such as `/ch1` or `/part-i`

## Risks

### Baseline scenario

Scripted, chunked translation succeeds with stable formatting and limited manual cleanup.

### Risk scenario

Large-file translation drifts in style, breaks Markdown structure, or truncates content. This is mitigated by chunked processing, per-file validation, and rerunnable generation.

## Non-Goals

- Adding `zh-cn` language configuration to `hugo.yaml`
- Syncing with `content/zh/`
- Publishing or deploying the translated output
