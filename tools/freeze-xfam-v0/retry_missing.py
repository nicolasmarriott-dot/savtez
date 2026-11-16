#!/usr/bin/env python3
"""Resend only the still-missing FREEZE-XFAM-v0 items on the same anonymous Space."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

for key in list(os.environ):
    if "TOKEN" in key.upper() or key in {
        "HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HF_API_TOKEN", "HUGGINGFACEHUB_API_TOKEN"
    }:
        if key == "HF_HUB_DISABLE_TELEMETRY":
            continue
        os.environ.pop(key, None)

assert not os.environ.get("HF_TOKEN")
assert not os.environ.get("HUGGING_FACE_HUB_TOKEN")

from gradio_client import Client
from huggingface_hub import get_token

assert get_token() is None, "refusing to run with a stored HF token"

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "examples" / "freeze-xfam-v0"
RAW = ROOT / "raw"
TASK = ROOT / "items-and-sources.txt"
RESULT = ROOT / "result.txt"
LOG = RAW / "calls.log"
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
RETRY_PREFIX = f"retry-{STAMP}"

SPACE = "bottlecapai/Qwen3.8-27B-reference"
MODEL_ID = "Qwen/Qwen3.8-27B"
PRECISION = "bf16"
MISSING = ["M022", "M023", "M024", "M025", "M100", "M125"]

ITEM_RE = re.compile(
    r"^(M\d{3})\s*\|\s*supported:\s*(yes|no)\s*\|\s*keeps:\s*(yes|no)\s*\|\s*ok:\s*(yes|no)\s*(?:\|\s*(.*))?$",
    re.IGNORECASE,
)
QUOTA_RE = re.compile(r"quota|out of gpu|zero.?gpu|pro to allow|subscribe|rate limit|429", re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    line = f"{utc_now()} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def build_prompt(wanted: list[str]) -> str:
    lines = TASK.read_text(encoding="utf-8").split("\n")
    assert lines[0] == "TO AI"
    si = lines.index("SOURCES")
    ii = lines.index("ITEMS")
    header = "\n".join(lines[1:si])
    src_lines = lines[si + 1 : ii]
    items = [l for l in lines[ii + 1 :] if re.match(r"^M\d{3} ", l)]
    blocks = {}
    order = []
    for l in src_lines:
        m = re.match(r"^\[(S\d+)\] ", l)
        if m:
            sid = m.group(1)
            if sid not in blocks:
                blocks[sid] = []
                order.append(sid)
            blocks[sid].append(l)
    batch = []
    for it in items:
        mid = it.split(" ", 1)[0]
        if mid in wanted:
            batch.append(it)
    assert [it.split(" ", 1)[0] for it in batch] == wanted, f"item order mismatch: {batch}"
    need = {re.match(r"^M\d{3} \[(S\d+)\]", it).group(1) for it in batch}
    parts = [header, "SOURCES"]
    for sid in order:
        if sid in need:
            parts.append("\n".join(blocks[sid]))
            parts.append("")
    parts.append("ITEMS")
    parts.extend(batch)
    return "\n".join(parts)


def extract_text(result) -> str:
    chunks: list[str] = []

    def walk(obj, from_assistant=False):
        if obj is None:
            return
        if isinstance(obj, str):
            chunks.append(obj)
            return
        if isinstance(obj, dict):
            role = obj.get("role")
            meta = obj.get("metadata") or {}
            if role == "assistant" and meta.get("title"):
                return
            if "content" in obj:
                walk(obj["content"], from_assistant=(role == "assistant" or from_assistant))
            elif "text" in obj:
                walk(obj["text"], from_assistant=from_assistant)
            else:
                for v in obj.values():
                    if isinstance(v, (list, dict, str)):
                        walk(v, from_assistant=from_assistant)
            return
        if isinstance(obj, (list, tuple)):
            for x in obj:
                walk(x, from_assistant=from_assistant)

    walk(result)
    return "\n".join(chunks)


def parse_items(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[\-\*\d\.\)\s`]+", "", line).strip()
        if line.startswith("```"):
            continue
        m = ITEM_RE.match(line) or ITEM_RE.search(line)
        if m:
            mid = m.group(1).upper()
            if mid in found:
                continue
            reason = (m.group(5) or "").strip()
            formatted = (
                f"{mid} | supported: {m.group(2).lower()} | "
                f"keeps: {m.group(3).lower()} | ok: {m.group(4).lower()}"
            )
            if reason:
                formatted += f" | {reason}"
            found[mid] = formatted
        elif re.search(r"\bM\d{3}\b", line):
            mid_m = re.search(r"\b(M\d{3})\b", line)
            mid = mid_m.group(1).upper()
            if mid not in found:
                found[mid] = f"{mid} | UNPARSED"
    return found


def is_quota_error(exc: BaseException) -> bool:
    return bool(QUOTA_RE.search(str(exc)))


def call_respond(client: Client, prompt: str, timeout: float = 600.0):
    job = client.submit(
        message={"text": prompt, "files": []},
        history=[],
        reasoning_effort="off",
        max_new_tokens=2048,
        temperature=1.0,
        top_p=0.95,
        top_k=20,
        api_name="/respond",
    )
    return job.result(timeout=timeout)


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    log(f"RETRY START route=anonymous gradio_client space={SPACE} model={MODEL_ID} precision={PRECISION} items={','.join(MISSING)}")
    log("token_check: get_token() is None; no HF_TOKEN in env")

    prompt = build_prompt(MISSING)
    prompt_path = RAW / f"{RETRY_PREFIX}.prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    log(f"wrote prompt {prompt_path} bytes={len(prompt)} items={MISSING}")

    try:
        log("connecting anonymously...")
        client = Client(SPACE)
        log(f"connected host={getattr(client, 'src', None)}")
        t0 = time.time()
        result = call_respond(client, prompt)
        elapsed = time.time() - t0
        text = extract_text(result)
        (RAW / f"{RETRY_PREFIX}.respond.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (RAW / f"{RETRY_PREFIX}.output.txt").write_text(text, encoding="utf-8")
        (RAW / f"{RETRY_PREFIX}.meta.json").write_text(
            json.dumps(
                {
                    "items": MISSING,
                    "started_or_finished": utc_now(),
                    "elapsed_s": round(elapsed, 1),
                    "endpoint": "/respond",
                    "prompt_bytes": len(prompt),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        parsed = parse_items(text)
        kept = {mid: parsed[mid] for mid in MISSING if mid in parsed}
        complete = {mid: line for mid, line in kept.items() if not line.endswith("| UNPARSED")}
        unparsed = [mid for mid, line in kept.items() if line.endswith("| UNPARSED")]
        still_missing = [mid for mid in MISSING if mid not in complete]
        log(
            f"RETRY DONE via /respond in {elapsed:.1f}s "
            f"complete={sorted(complete)} unparsed={unparsed} still_missing={still_missing}"
        )
        # Signal to the caller via a machine-readable sidecar
        (RAW / f"{RETRY_PREFIX}.parsed.json").write_text(
            json.dumps(
                {
                    "complete": complete,
                    "unparsed": {mid: kept[mid] for mid in unparsed},
                    "still_missing": still_missing,
                    "quota_blocked": False,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print("SIDECAR", RAW / f"{RETRY_PREFIX}.parsed.json")
        return 0
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        blocked = is_quota_error(e)
        log(f"RETRY FAIL blocked={blocked}: {err}")
        (RAW / f"{RETRY_PREFIX}.error.txt").write_text(
            f"{utc_now()}\n{err}\n{traceback.format_exc()}", encoding="utf-8"
        )
        (RAW / f"{RETRY_PREFIX}.parsed.json").write_text(
            json.dumps(
                {
                    "complete": {},
                    "unparsed": {},
                    "still_missing": MISSING,
                    "quota_blocked": blocked,
                    "error": err,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print("SIDECAR", RAW / f"{RETRY_PREFIX}.parsed.json")
        # Do not touch result.txt on failure
        return 2 if blocked else 1


if __name__ == "__main__":
    sys.exit(main())
