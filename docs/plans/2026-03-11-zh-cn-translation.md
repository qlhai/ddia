# content/en to content/zh-cn Translation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild `content/zh-cn/` from `content/en/` by translating each Markdown file directly from English into Simplified Chinese while preserving repository-specific Markdown structure.

**Architecture:** Add a small local translation pipeline under `bin/` that enumerates English Markdown files, translates body content in a structure-preserving manner, writes output into `content/zh-cn/`, and then runs repository-specific validation checks. Keep the pipeline deterministic and avoid any dependency on `content/zh/`.

**Tech Stack:** Python 3, repository Markdown files, shell verification commands

---

### Task 1: Inspect source corpus and target directory

**Files:**
- Read: `content/en/*.md`
- Read/Remove: `content/zh-cn/*.md`

**Step 1: Count English source files**

Run: `find content/en -maxdepth 1 -name '*.md' | sort | wc -l`
Expected: `23`

**Step 2: Inspect current target directory state**

Run: `find content/zh-cn -maxdepth 1 -name '*.md' 2>/dev/null | sort`
Expected: existing files are listed or no output

**Step 3: Remove old target content**

Run: `rm -rf content/zh-cn && mkdir -p content/zh-cn`
Expected: empty `content/zh-cn/` exists

**Step 4: Commit planning docs**

```bash
git add docs/plans/2026-03-11-zh-cn-translation-design.md docs/plans/2026-03-11-zh-cn-translation.md
git commit -m "docs(plan): 添加 zh-cn 翻译设计与实施计划"
```

### Task 2: Create a translation driver

**Files:**
- Create: `bin/translate_zh_cn.py`

**Step 1: Write the CLI skeleton**

Create a script that:
- reads `content/en/*.md`
- rewrites `content/zh-cn/*.md`
- refuses to read from `content/zh/`

**Step 2: Add file processing structure**

Implement functions for:
- reading a Markdown file
- splitting front matter and body
- writing output with UTF-8 encoding

**Step 3: Add safe directory rebuild**

Implement target directory recreation inside the script so repeated runs are deterministic.

**Step 4: Run a syntax smoke check**

Run: `python3 -m py_compile bin/translate_zh_cn.py`
Expected: no output

**Step 5: Commit**

```bash
git add bin/translate_zh_cn.py
git commit -m "feat(translation): 添加 zh-cn 翻译脚本骨架"
```

### Task 3: Implement Markdown-preserving translation logic

**Files:**
- Modify: `bin/translate_zh_cn.py`

**Step 1: Define protected Markdown regions**

Implement detection or segmentation for:
- front matter
- fenced code blocks
- inline code
- raw HTML anchors
- URLs
- footnote markers

**Step 2: Implement translatable text handling**

Translate only natural-language text segments, keeping Markdown markers unchanged.

**Step 3: Encode terminology rules**

Add a small terminology map or hook so repeated technical terms remain consistent.

**Step 4: Run script on one sample file**

Run: `python3 bin/translate_zh_cn.py --files ch1.md`
Expected: `content/zh-cn/ch1.md` is created and structurally intact

**Step 5: Inspect sample output**

Run: `sed -n '1,120p' content/zh-cn/ch1.md`
Expected: front matter is preserved and body is Simplified Chinese

**Step 6: Commit**

```bash
git add bin/translate_zh_cn.py content/zh-cn/ch1.md
git commit -m "feat(translation): 实现 Markdown 结构保留翻译"
```

### Task 4: Implement internal link rewriting

**Files:**
- Modify: `bin/translate_zh_cn.py`

**Step 1: Add chapter-link rewrite rules**

Rewrite only these root-style links when they target book pages:
- `/ch1` through `/ch14`
- `/part-i`, `/part-ii`, `/part-iii`
- `/preface`, `/glossary`, `/colophon`, `/indexes`, `/toc`

**Step 2: Keep non-chapter links unchanged**

Do not rewrite:
- image paths
- `/map/...`, `/fig/...`, `/logo.png`
- external URLs

**Step 3: Re-run sample generation**

Run: `python3 bin/translate_zh_cn.py --files toc.md part-i.md`
Expected: chapter-style links now point to `/zh-cn/...`

**Step 4: Verify rewritten links**

Run: `rg -n '\\]\\(/zh-cn/' content/zh-cn/toc.md content/zh-cn/part-i.md`
Expected: matches are found

**Step 5: Commit**

```bash
git add bin/translate_zh_cn.py content/zh-cn/toc.md content/zh-cn/part-i.md
git commit -m "feat(translation): 添加 zh-cn 章节链接重写"
```

### Task 5: Generate the full corpus

**Files:**
- Modify/Create: `content/zh-cn/*.md`

**Step 1: Run full generation**

Run: `python3 bin/translate_zh_cn.py`
Expected: all translated files are written to `content/zh-cn/`

**Step 2: Verify file count**

Run: `find content/en -maxdepth 1 -name '*.md' | sort | wc -l && find content/zh-cn -maxdepth 1 -name '*.md' | sort | wc -l`
Expected: both counts are `23`

**Step 3: Verify filename parity**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
en={p.name for p in Path('content/en').glob('*.md')}
zhcn={p.name for p in Path('content/zh-cn').glob('*.md')}
print('missing', sorted(en-zhcn))
print('extra', sorted(zhcn-en))
PY
```

Expected: both lists are empty

**Step 4: Commit**

```bash
git add content/zh-cn
git commit -m "feat(content): 生成 zh-cn 全量翻译稿"
```

### Task 6: Verify structure and link safety

**Files:**
- Read: `content/zh-cn/*.md`

**Step 1: Check for residual root chapter links**

Run: `rg -n '\\]\\(/(ch(?:1[0-4]|[1-9])|part-i|part-ii|part-iii|preface|glossary|colophon|indexes|toc)([#)])' content/zh-cn`
Expected: no matches

**Step 2: Check that code fences still exist**

Run: `rg -n '^```' content/en content/zh-cn | sed -n '1,40p'`
Expected: fences appear in both trees

**Step 3: Spot-check several generated chapters**

Run:

```bash
sed -n '1,80p' content/zh-cn/ch1.md
sed -n '1,80p' content/zh-cn/ch8.md
sed -n '1,80p' content/zh-cn/glossary.md
```

Expected: Simplified Chinese text, intact front matter, intact anchors

**Step 4: Commit**

```bash
git add content/zh-cn
git commit -m "fix(translation): 校正 zh-cn 结构与链接问题"
```

### Task 7: Final verification

**Files:**
- Read: `bin/translate_zh_cn.py`
- Read: `content/zh-cn/*.md`

**Step 1: Run the generator again to confirm reproducibility**

Run: `python3 bin/translate_zh_cn.py`
Expected: no unexpected failures

**Step 2: Confirm clean working tree or expected diffs only**

Run: `git status --short`
Expected: clean, or only intentional unstaged changes

**Step 3: Summarize remaining risks**

Document any chapters that need manual terminology review or quote polishing.

**Step 4: Final commit if needed**

```bash
git add bin/translate_zh_cn.py content/zh-cn
git commit -m "chore(translation): 完成 zh-cn 直译流水线校验"
```
