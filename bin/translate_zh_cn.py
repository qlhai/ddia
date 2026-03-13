#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shlex
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "content" / "en"
TARGET_DIR = ROOT / "content" / "zh-cn"
FORBIDDEN_DIR = ROOT / "content" / "zh"
CHECKPOINT_DIR = TARGET_DIR / ".translation-checkpoints"

CHAPTER_LINK_RE = re.compile(
    r"\]\(/(?:en/)?(ch(?:1[0-4]|[1-9])|part-i|part-ii|part-iii|preface|glossary|colophon|indexes|toc)(#[^)]+)?\)"
)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
FOOTNOTE_MARKER_RE = re.compile(r"\[\^[^\]]+\]")
URL_RE = re.compile(r"https?://[^\s)]+")
HTML_TAG_RE = re.compile(r"<[^>]+>")

TERMINOLOGY = {
    "data-intensive": "数据密集型（data-intensive）",
    "compute-intensive": "计算密集型（compute-intensive）",
    "batch processing": "批处理（batch processing）",
    "stream processing": "流处理（stream processing）",
}
DEFAULT_MAX_SEGMENT_CHARS = 5000
CHECKPOINT_SCHEMA_VERSION = 2

TRANSLATION_STYLE_PROMPT = """
你是严谨的翻译助理。请将输入的 Markdown 内容翻译为简体中文，并严格遵守下列规则。

【总原则】
采用“内精外简”模式：
- 先在内部使用 English 或现代汉语完成分析、判断、比较、预测。
- 内部分析时，以逻辑严密、术语准确、条件完整为先。
- 不展示内部推理过程，不输出分析草稿，不输出中间版本。
- 对外只输出最终答案。

【文体规则】
1. 结论、判断、总结、过渡，用简洁文言或半文言。
2. 不用口语、不寒暄、不抒情、不用 Emoji。
3. 不刻意仿古，不用生僻典故，不作骈俪堆砌。
4. 句宜短，意宜明，宁直勿华。
5. 若纯文言可能致歧义，则改用半文半白，以保精确。

【逻辑规则】
1. 先下结论，后陈理由。
2. 明示前提、适用条件、边界、例外、风险。
3. 若有不确定处，须直言“此为推测”或“信息不足”。
4. 不得以文害意，不得因求简而省略关键条件。
5. 若涉及比较、取舍、优劣判断，须说明判断所据，不可只下断语。
6. 若涉及复杂因果链、条件分支、性能瓶颈、例外路径，必须显式写出，不得省略。

【预测与估计规则】
1. 若涉及预测、趋势、概率、估计、风险判断，先说明前提。
2. 须区分“较确定事实”与“此为推测”。
3. 须给出主要影响因素。
4. 若存在多种情景，至少区分“基准情景”与“风险情景”。
5. 不可将预测写成无条件断言。

【术语规则】
1. 现代术语、专有名词、库名、协议名、药名、法律名、金融名、标准名，保留英文或标准现代术语。
2. 不强行将 technical terms 翻为文言。
3. 术语首次出现时，可用“极简中文解释 + 原术语”并列。
4. 涉及代码、系统设计、医学、法律、金融等高精度内容时，以术语准确为先，不为文雅让步。

【格式规则】
1. 默认按以下顺序输出：结论 → 原因 → 条件/边界 → 建议/示例。
2. 若任务复杂，可先给极简结论，再分项说明。
3. 若需分点，可用“其一、其二、其三”；非必要，不滥列条目。
4. 代码、JSON、SQL、XML、YAML、正则、命令、配置、接口字段、表格、公式，必须使用标准格式，不作文言改写。
5. 结构化内容须可直接复制使用，不得为求古雅而改动语法、字段名、关键字、保留字、协议字面量。

【质量规则】
1. 以准确、完整、可执行为先，文雅为后。
2. 宁可半文半白以保清楚，不可为求古雅而生歧义。
3. 输出应凝练，但不得牺牲信息密度与可操作性。
4. 若输入本身存在歧义、信息缺口或前提不足，须明确指出，再于现有前提下给出最佳可行译文。
5. 不得编造事实、来源、数据、结论；不确定者明言不确定。

【禁止事项】
1. 禁止输出内部推理过程。
2. 禁止伪古文、空话、套话、典故堆砌。
3. 禁止把现代复杂概念粗暴古文化。
4. 禁止因求简短而省略定义、限制条件、例外情况、风险提示。
5. 禁止输出无信息增量的开场白、总结腔、模板腔。
6. 禁止使用 items、Emoji、夸张语气、营销式表达。

【执行细则】
1. 先在内部完成精确分析，再将“自然语言叙述层”压缩改写为简洁文言或半文言。
2. 专业术语层、逻辑条件层、结构化表达层，一律保持现代精确表达。
3. 若内容属于技术实现、代码、协议说明等高精度内容，则文言仅用于说明文字，不进入专业内容本体。
4. 仅输出翻译后的 Markdown，不加任何解释。

另加技术约束：
- Preserve Markdown structure exactly.
- Preserve code spans, code fences, footnote markers, URLs, HTML tags, and link destinations.
- Translate natural language only.
- Keep the output as Markdown only, with no commentary.
""".strip()

TITLE_TRANSLATION_PROMPT = """
将输入标题翻译为简体中文。
要求：
- 只输出译文，不加解释，不加引号，不加提示语。
- 保留专有名词、必要英文术语、缩写与数字。
- 文风简洁准确，可略带半文半白，但不得故作艰深。
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Translate content/en Markdown files into content/zh-cn without using content/zh."
    )
    parser.add_argument("--files", nargs="+", help="Optional subset of file names under content/en")
    parser.add_argument(
        "--backend",
        choices=("cmd", "openai_compatible"),
        default=os.environ.get("TRANSLATOR_BACKEND", "openai_compatible"),
        help="Translation backend.",
    )
    parser.add_argument(
        "--translator-cmd",
        default=os.environ.get("TRANSLATOR_CMD", ""),
        help="External translator command for the cmd backend.",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("OPENAI_API_KEY", ""),
        help="Primary OpenAI-compatible API key.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get(
            "OPENAI_COMPAT_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
        ),
        help="Primary OpenAI-compatible base URL.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OPENAI_COMPAT_MODEL", "qwen-plus"),
        help="Primary OpenAI-compatible model.",
    )
    parser.add_argument(
        "--fallback-api-key",
        default=os.environ.get("FALLBACK_OPENAI_API_KEY", ""),
        help="Fallback OpenAI-compatible API key.",
    )
    parser.add_argument(
        "--fallback-base-url",
        default=os.environ.get("FALLBACK_OPENAI_COMPAT_BASE_URL", "https://api.deepseek.com/v1"),
        help="Fallback OpenAI-compatible base URL.",
    )
    parser.add_argument(
        "--fallback-model",
        default=os.environ.get("FALLBACK_OPENAI_COMPAT_MODEL", "deepseek-chat"),
        help="Fallback OpenAI-compatible model.",
    )
    parser.add_argument(
        "--insecure-ssl",
        action="store_true",
        default=os.environ.get("TRANSLATOR_INSECURE_SSL", "") == "1",
        help="Disable SSL certificate verification for HTTPS requests.",
    )
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=int(os.environ.get("TRANSLATOR_REQUEST_TIMEOUT", "60")),
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--min-request-interval",
        type=float,
        default=float(os.environ.get("TRANSLATOR_MIN_REQUEST_INTERVAL", "5")),
        help="Minimum seconds to wait after each successful request.",
    )
    parser.add_argument(
        "--max-request-interval",
        type=float,
        default=float(os.environ.get("TRANSLATOR_MAX_REQUEST_INTERVAL", "60")),
        help="Maximum seconds to wait after each successful request.",
    )
    parser.add_argument(
        "--keep-target",
        action="store_true",
        help="Do not recreate content/zh-cn before writing output.",
    )
    parser.add_argument(
        "--max-segments",
        type=int,
        default=0,
        help="Translate at most this many body segments per file. 0 means no limit.",
    )
    parser.add_argument(
        "--max-segment-chars",
        type=int,
        default=int(os.environ.get("TRANSLATOR_MAX_SEGMENT_CHARS", str(DEFAULT_MAX_SEGMENT_CHARS))),
        help="Maximum approximate characters per translated body segment.",
    )
    parser.add_argument(
        "--provider-cycle-retries",
        type=int,
        default=int(os.environ.get("TRANSLATOR_PROVIDER_CYCLE_RETRIES", "3")),
        help="How many full provider cycles to try before failing a segment.",
    )
    parser.add_argument(
        "--provider-cycle-backoff",
        type=float,
        default=float(os.environ.get("TRANSLATOR_PROVIDER_CYCLE_BACKOFF", "30")),
        help="Seconds to sleep between failed provider cycles.",
    )
    return parser.parse_args()


def ensure_allowed_paths() -> None:
    if FORBIDDEN_DIR.exists() and FORBIDDEN_DIR.resolve() in SOURCE_DIR.resolve().parents:
        raise RuntimeError("Unexpected source layout.")


def build_profiles(args: argparse.Namespace) -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    if args.backend == "cmd":
        profiles.append({"type": "cmd", "name": "cmd", "command": args.translator_cmd})
        return profiles
    profiles.append(
        {
            "type": "openai_compatible",
            "name": "primary",
            "api_key": args.api_key,
            "base_url": args.base_url,
            "model": args.model,
        }
    )
    if args.fallback_api_key:
        profiles.append(
            {
                "type": "openai_compatible",
                "name": "fallback",
                "api_key": args.fallback_api_key,
                "base_url": args.fallback_base_url,
                "model": args.fallback_model,
            }
        )
    return profiles


def discover_files(requested: list[str] | None) -> list[Path]:
    if requested:
        files = [SOURCE_DIR / name for name in requested]
    else:
        files = sorted(SOURCE_DIR.glob("*.md"))
    missing = [str(path.name) for path in files if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing source files: {', '.join(missing)}")
    return files


def recreate_target_dir(keep_target: bool) -> None:
    if keep_target:
        TARGET_DIR.mkdir(parents=True, exist_ok=True)
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        return
    shutil.rmtree(TARGET_DIR, ignore_errors=True)
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


def split_front_matter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("Unclosed front matter block.")
    front_matter = text[: end + 5]
    body = text[end + 5 :]
    return front_matter, body


def rewrite_chapter_links(text: str) -> str:
    text = CHAPTER_LINK_RE.sub(lambda m: f"](/zh-cn/{m.group(1)}{m.group(2) or ''})", text)
    text = re.sub(
        r"\((/en/(?:ch(?:1[0-4]|[1-9])|part-i|part-ii|part-iii|preface|glossary|colophon|indexes|toc)(?:#[^)]+)?)\)",
        lambda m: f"({m.group(1).replace('/en/', '/zh-cn/')})",
        text,
    )
    return text.replace("](/)", "](/zh-cn/)")


def mask_patterns(text: str) -> tuple[str, dict[str, str]]:
    replacements: dict[str, str] = {}
    counter = 0

    def mask(regex: re.Pattern[str], current: str) -> str:
        nonlocal counter

        def replace(match: re.Match[str]) -> str:
            nonlocal counter
            token = f"__MASK_{counter}__"
            replacements[token] = match.group(0)
            counter += 1
            return token

        return regex.sub(replace, current)

    masked = text
    for regex in (INLINE_CODE_RE, FOOTNOTE_MARKER_RE, URL_RE, HTML_TAG_RE):
        masked = mask(regex, masked)
    return masked, replacements


def unmask_patterns(text: str, replacements: dict[str, str]) -> str:
    restored = text
    for token, original in replacements.items():
        restored = restored.replace(token, original)
    return restored


def apply_terminology(text: str) -> str:
    updated = text
    for source, target in TERMINOLOGY.items():
        updated = re.sub(rf"\b{re.escape(source)}\b", target, updated, flags=re.IGNORECASE)
    return updated


def run_command_translator(command: str, text: str) -> str:
    if not command:
        raise RuntimeError("No translation command configured. Set TRANSLATOR_CMD or pass --translator-cmd.")
    process = subprocess.run(
        shlex.split(command),
        input=text,
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(
            f"Translation command failed with exit code {process.returncode}: {process.stderr.strip()}"
        )
    output = process.stdout.strip()
    if not output:
        raise RuntimeError("Translation command returned empty output.")
    return output


def run_openai_compatible_translator(
    text: str,
    profile: dict[str, str],
    insecure_ssl: bool,
    request_timeout: int,
    system_prompt: str,
) -> str:
    api_key = profile["api_key"]
    if not api_key:
        raise RuntimeError(f"No API key configured for {profile['name']} profile.")
    payload = json.dumps(
        {
            "model": profile["model"],
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{profile['base_url'].rstrip('/')}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    context = ssl._create_unverified_context() if insecure_ssl else None
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=request_timeout, context=context) as response:
                body = json.loads(response.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"].strip()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            status = getattr(exc, "code", None)
            if status == 403:
                raise RuntimeError(f"HTTP 403 from {profile['name']} profile") from exc
            if attempt == 2:
                raise RuntimeError(
                    f"{profile['name']} request failed after 3 attempts: {exc}"
                ) from exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{profile['name']} request failed: {last_error}")


def run_translator(
    args: argparse.Namespace,
    state: dict[str, object],
    text: str,
    system_prompt: str = TRANSLATION_STYLE_PROMPT,
) -> str:
    profiles: list[dict[str, str]] = state["profiles"]  # type: ignore[assignment]
    active_index = int(state.get("active_profile_index", 0))
    if profiles[active_index]["type"] == "cmd":
        return run_command_translator(profiles[active_index]["command"], text)

    profile_count = len(profiles)
    last_error: Exception | None = None
    for cycle in range(args.provider_cycle_retries):
        for offset in range(profile_count):
            index = (active_index + offset) % profile_count
            profile = profiles[index]
            try:
                result = run_openai_compatible_translator(
                    text=text,
                    profile=profile,
                    insecure_ssl=args.insecure_ssl,
                    request_timeout=args.request_timeout,
                    system_prompt=system_prompt,
                )
                if index != active_index:
                    print(
                        f"  switch translator to {profile['name']} ({profile['model']})",
                        file=sys.stderr,
                    )
                    state["active_profile_index"] = index
                return result
            except RuntimeError as exc:
                last_error = exc
                print(f"  {profile['name']} failed: {exc}", file=sys.stderr)
                continue
        if cycle < args.provider_cycle_retries - 1:
            print(
                f"  all providers failed; backoff {args.provider_cycle_backoff:.1f}s before retry",
                file=sys.stderr,
            )
            time.sleep(args.provider_cycle_backoff)
    raise RuntimeError(str(last_error) if last_error else "Translation failed.")


def translate_text(
    text: str,
    args: argparse.Namespace,
    state: dict[str, object],
    system_prompt: str = TRANSLATION_STYLE_PROMPT,
) -> str:
    if not text.strip():
        return text
    masked, replacements = mask_patterns(text.rstrip("\n"))
    translated = run_translator(args, state, masked, system_prompt=system_prompt)
    translated = apply_terminology(translated)
    translated = unmask_patterns(translated, replacements)
    return translated + ("\n" if text.endswith("\n") else "")


def split_body_into_segments(body: str, max_segment_chars: int) -> list[dict[str, object]]:
    segments: list[dict[str, object]] = []
    in_code_block = False
    buffer: list[str] = []
    buffer_chars = 0

    def flush_buffer() -> None:
        nonlocal buffer_chars
        if not buffer:
            return
        text = "".join(buffer)
        if text.strip():
            segments.append({"kind": "translate", "text": text})
        else:
            segments.append({"kind": "raw", "text": text})
        buffer.clear()
        buffer_chars = 0

    for line in body.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_buffer()
            in_code_block = not in_code_block
            segments.append({"kind": "raw", "text": line})
            continue
        if in_code_block:
            segments.append({"kind": "raw", "text": line})
            continue
        if stripped.startswith("<a ") and stripped.endswith(">"):
            flush_buffer()
            segments.append({"kind": "raw", "text": line})
            continue
        if stripped.startswith("[^") and "]: " in stripped:
            flush_buffer()
            segments.append({"kind": "raw", "text": line})
            continue
        if stripped.startswith("#"):
            flush_buffer()
            segments.append({"kind": "translate", "text": line})
            continue
        if stripped.startswith("{{<") or stripped.startswith("{{%"):
            flush_buffer()
            segments.append({"kind": "raw", "text": line})
            continue
        buffer.append(line)
        buffer_chars += len(line)
        if buffer_chars >= max_segment_chars:
            flush_buffer()
    flush_buffer()
    return segments


def checkpoint_path_for(source_path: Path) -> Path:
    return CHECKPOINT_DIR / f"{source_path.name}.json"


def compute_source_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_checkpoint(source_path: Path, source_digest: str) -> dict[str, object] | None:
    path = checkpoint_path_for(source_path)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        return None
    if data.get("source_digest") != source_digest:
        return None
    return data


def save_checkpoint(source_path: Path, checkpoint: dict[str, object]) -> None:
    path = checkpoint_path_for(source_path)
    path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")


def translate_front_matter(front_matter: str, args: argparse.Namespace, state: dict[str, object]) -> str:
    if not front_matter:
        return front_matter
    output: list[str] = []
    for line in front_matter.splitlines(keepends=True):
        if line.startswith("title:"):
            prefix, raw_value = line.split(":", 1)
            value = raw_value.strip()
            quote = ""
            if value[:1] in {'"', "'"} and value[-1:] == value[:1]:
                quote = value[:1]
                value = value[1:-1]
            translated = translate_text(
                value, args, state, system_prompt=TITLE_TRANSLATION_PROMPT
            ).rstrip("\n")
            if "请提供需翻译" in translated:
                raise RuntimeError("Title translation returned a prompt, not a title.")
            if quote:
                output.append(f"{prefix}: {quote}{translated}{quote}\n")
            else:
                output.append(f"{prefix}: {translated}\n")
            continue
        output.append(line)
    return "".join(output)


def write_progress_output(
    target_path: Path,
    translated_front_matter: str,
    rendered_segments: list[str],
) -> None:
    target_path.write_text(
        translated_front_matter + rewrite_chapter_links("".join(rendered_segments)),
        encoding="utf-8",
    )


def translate_file(path: Path, args: argparse.Namespace, state: dict[str, object]) -> None:
    text = path.read_text(encoding="utf-8")
    source_digest = compute_source_digest(text)
    front_matter, body = split_front_matter(text)
    target_path = TARGET_DIR / path.name

    checkpoint = load_checkpoint(path, source_digest)

    segments = split_body_into_segments(body, args.max_segment_chars)
    full_translatable_total = sum(1 for segment in segments if segment["kind"] == "translate")
    translatable_total = full_translatable_total
    if args.max_segments:
        translatable_total = min(translatable_total, args.max_segments)

    if checkpoint and checkpoint.get("completed"):
        if int(checkpoint.get("completed_translatable", 0)) >= full_translatable_total:
            print(f"Skip completed {path.name}", file=sys.stderr)
            return
        checkpoint["completed"] = False

    if checkpoint:
        translated_front_matter = str(checkpoint["translated_front_matter"])
        rendered_segments = [str(item) for item in checkpoint["rendered_segments"]]
        completed_translatable = int(checkpoint["completed_translatable"])
        segment_index = int(checkpoint["segment_index"])
        print(
            f"Resume {path.name} from segment {segment_index + 1}, completed {completed_translatable}",
            file=sys.stderr,
        )
    else:
        translated_front_matter = translate_front_matter(front_matter, args, state)
        rendered_segments = []
        completed_translatable = 0
        segment_index = 0
        save_checkpoint(
            path,
            {
                "source_digest": source_digest,
                "schema_version": CHECKPOINT_SCHEMA_VERSION,
                "completed": False,
                "translated_front_matter": translated_front_matter,
                "completed_translatable": completed_translatable,
                "segment_index": segment_index,
                "rendered_segments": rendered_segments,
            },
        )
        write_progress_output(target_path, translated_front_matter, rendered_segments)

    for idx in range(segment_index, len(segments)):
        segment = segments[idx]
        if segment["kind"] == "raw":
            rendered_segments.append(str(segment["text"]))
        else:
            if args.max_segments and completed_translatable >= args.max_segments:
                rendered_segments.append(str(segment["text"]))
            else:
                print(
                    f"  segment {completed_translatable + 1}/{translatable_total}...",
                    file=sys.stderr,
                )
                rendered_segments.append(translate_text(str(segment["text"]), args, state))
                completed_translatable += 1
                if args.max_request_interval > 0:
                    sleep_min = min(args.min_request_interval, args.max_request_interval)
                    sleep_max = max(args.min_request_interval, args.max_request_interval)
                    sleep_seconds = random.uniform(sleep_min, sleep_max)
                    print(f"  sleep {sleep_seconds:.1f}s", file=sys.stderr)
                    time.sleep(sleep_seconds)
        next_index = idx + 1
        save_checkpoint(
            path,
            {
                "source_digest": source_digest,
                "schema_version": CHECKPOINT_SCHEMA_VERSION,
                "completed": False,
                "translated_front_matter": translated_front_matter,
                "completed_translatable": completed_translatable,
                "segment_index": next_index,
                "rendered_segments": rendered_segments,
            },
        )
        write_progress_output(target_path, translated_front_matter, rendered_segments)

    save_checkpoint(
        path,
        {
            "source_digest": source_digest,
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "completed": completed_translatable >= full_translatable_total,
            "translated_front_matter": translated_front_matter,
            "completed_translatable": completed_translatable,
            "segment_index": len(segments),
            "rendered_segments": rendered_segments,
        },
    )


def main() -> int:
    args = parse_args()
    ensure_allowed_paths()
    files = discover_files(args.files)
    recreate_target_dir(args.keep_target)
    state: dict[str, object] = {
        "profiles": build_profiles(args),
        "active_profile_index": 0,
    }
    for path in files:
        print(f"Translating {path.name}...", file=sys.stderr)
        translate_file(path, args, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
