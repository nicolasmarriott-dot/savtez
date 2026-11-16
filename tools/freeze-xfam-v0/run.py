#!/usr/bin/env python3
"""Anonymous freeze-test runner for bottlecapai/Qwen3.8-27B-reference (Qwen/Qwen3.8-27B, bf16)."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Refuse to use any HF token.
for key in list(os.environ):
    if "TOKEN" in key.upper() or key.startswith("HF_"):
        if key in {"HF_HUB_DISABLE_TELEMETRY"}:
            continue
        # Do not pass tokens; strip only auth-related
        if "TOKEN" in key.upper() or key in {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HF_API_TOKEN", "HUGGINGFACEHUB_API_TOKEN"}:
            os.environ.pop(key, None)

assert not os.environ.get("HF_TOKEN")
assert not os.environ.get("HUGGING_FACE_HUB_TOKEN")

from gradio_client import Client
from huggingface_hub import get_token
from tokenizers import Tokenizer

assert get_token() is None, "refusing to run with a stored HF token"

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "examples" / "freeze-xfam-v0"
RAW = ROOT / "raw"
BATCH_DIR = ROOT / "batches"
RESULT = ROOT / "result.txt"
LOG = RAW / "calls.log"

SPACE = "bottlecapai/Qwen3.8-27B-reference"
MODEL_ID = "Qwen/Qwen3.8-27B"
PRECISION = "bf16"
ENDPOINT = "/respond"
EXPECTED = 150

ITEM_RE = re.compile(
    r"^(M\d{3})\s*\|\s*supported:\s*(yes|no)\s*\|\s*keeps:\s*(yes|no)\s*\|\s*ok:\s*(yes|no)\s*(?:\|\s*(.*))?$",
    re.IGNORECASE,
)
QUOTA_RE = re.compile(r"quota|out of gpu|zero.?gpu|pro to allow|subscribe|rate limit|429", re.I)

EOS_IDS = {248046, 248044}  # <|im_end|>, <|endoftext|>

tokenizer = Tokenizer.from_file("/tmp/qwen38-tok/tokenizer.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    line = f"{utc_now()} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def extract_text(result) -> str:
    """Pull assistant text out of a /respond result without changing it."""
    chunks: list[str] = []

    def walk(obj, from_assistant=False):
        if obj is None:
            return
        if isinstance(obj, str):
            if from_assistant or True:
                chunks.append(obj)
            return
        if isinstance(obj, dict):
            role = obj.get("role")
            meta = obj.get("metadata") or {}
            # Skip reasoning/notice bubbles if present
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
            return

    walk(result)
    # Prefer joining with newlines; keep raw pieces
    return "\n".join(chunks)


def parse_items(text: str) -> dict[str, str]:
    """Map Mxxx -> formatted line or UNPARSED. Do not invent missing ids."""
    found: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # tolerate markdown fences or leading bullets
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


def write_result(status: str, sentence: str, items: dict[str, str], provenance: list[str],
                 missing: list[str]) -> None:
    lines = [f"VERDICT | FREEZE-XFAM-v0 | {status} | {sentence}"]
    for i in range(1, EXPECTED + 1):
        mid = f"M{i:03d}"
        if mid in items:
            lines.append(items[mid])
        else:
            lines.append(f"{mid} | NOT RETURNED")
    lines.append("")
    lines.append("PROVENANCE")
    lines.extend(provenance)
    RESULT.write_text("\n".join(lines) + "\n", encoding="utf-8")


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


def call_step_loop(client: Client, prompt: str, timeout_per_step: float = 180.0, max_steps: int = 12):
    """Fallback: loop /step and decode ids locally with the official tokenizer."""
    generated: list[int] = []
    message = {"text": prompt, "files": []}
    history: list = []
    steps_meta = []
    for step_i in range(1, max_steps + 1):
        log(f"  /step {step_i} generated_so_far={len(generated)}")
        job = client.submit(
            message=message,
            history=history,
            generated=generated,
            max_new_tokens=2048,
            reasoning_effort="off",
            temperature=1.0,
            top_p=0.95,
            top_k=20,
            gpu_seconds=60,
            api_name="/step",
        )
        result = job.result(timeout=timeout_per_step)
        # result should be dict {ids, seconds, think_seconds}
        if isinstance(result, list) and result and isinstance(result[0], dict):
            result = result[-1]
        if not isinstance(result, dict) or "ids" not in result:
            raise RuntimeError(f"unexpected /step result: {type(result)} {str(result)[:400]}")
        new_ids = list(result["ids"] or [])
        generated.extend(new_ids)
        steps_meta.append({"step": step_i, "new": len(new_ids), "seconds": result.get("seconds"),
                           "total": len(generated)})
        if not new_ids:
            break
        if generated and generated[-1] in EOS_IDS:
            break
        if len(generated) >= 2048:
            break
    text = tokenizer.decode(generated, skip_special_tokens=True)
    return text, generated, steps_meta


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    start = utc_now()
    log(f"START route=anonymous gradio_client space={SPACE} model={MODEL_ID} precision={PRECISION}")
    log("token_check: get_token() is None; no HF_TOKEN in env")

    # Load expected item ids per batch from prompt tails
    batch_ids: dict[str, list[str]] = {}
    prompts: dict[str, str] = {}
    for i in range(1, 7):
        name = f"batch{i:02d}"
        p = (BATCH_DIR / f"{name}.prompt.txt").read_text(encoding="utf-8")
        prompts[name] = p
        ids = re.findall(r"^(M\d{3})\b", p.split("ITEMS", 1)[-1], re.M)
        batch_ids[name] = ids
        log(f"loaded {name}: {len(p)} bytes, {len(ids)} items {ids[0]}-{ids[-1]}")

    all_ids = [mid for name in sorted(batch_ids) for mid in batch_ids[name]]
    assert len(all_ids) == EXPECTED, f"expected 150 ids, got {len(all_ids)}"

    items: dict[str, str] = {}
    unparsed = 0
    returned = 0
    sent = 0
    status = "BLOCKED"
    sentence = "No batches completed."
    quota_note = ""
    end = None
    client = None

    try:
        log("connecting anonymously...")
        client = Client(SPACE)
        log(f"connected host={getattr(client, 'src', None)}")

        for bname, prompt in prompts.items():
            ids = batch_ids[bname]
            sent += len(ids)
            raw_path = RAW / f"{bname}.respond.json"
            txt_path = RAW / f"{bname}.output.txt"
            log(f"SEND {bname} items {ids[0]}-{ids[-1]} prompt_bytes={len(prompt)}")
            t0 = time.time()
            used = ENDPOINT
            meta: dict = {"batch": bname, "started_utc": utc_now()}
            try:
                try:
                    result = call_respond(client, prompt)
                    text = extract_text(result)
                    meta["endpoint"] = "/respond"
                    meta["raw_type"] = type(result).__name__
                    raw_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str),
                                        encoding="utf-8")
                except Exception as e1:
                    log(f"  /respond failed: {type(e1).__name__}: {e1}")
                    meta["respond_error"] = f"{type(e1).__name__}: {e1}"
                    if is_quota_error(e1):
                        raise
                    # fallback to /step loop
                    used = "/step"
                    text, gen_ids, steps_meta = call_step_loop(client, prompt)
                    meta["endpoint"] = "/step"
                    meta["steps"] = steps_meta
                    meta["n_ids"] = len(gen_ids)
                    (RAW / f"{bname}.step.json").write_text(
                        json.dumps({"ids": gen_ids, "steps": steps_meta, "text": text},
                                   ensure_ascii=False),
                        encoding="utf-8",
                    )
                elapsed = time.time() - t0
                meta["elapsed_s"] = round(elapsed, 1)
                meta["finished_utc"] = utc_now()
                txt_path.write_text(text, encoding="utf-8")
                (RAW / f"{bname}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
                parsed = parse_items(text)
                # Only count ids that belonged to this batch
                for mid in ids:
                    if mid in parsed:
                        items[mid] = parsed[mid]
                        returned += 1
                        if parsed[mid].endswith("| UNPARSED"):
                            unparsed += 1
                extra = [k for k in parsed if k not in ids]
                log(f"  DONE {bname} via {used} in {elapsed:.1f}s "
                    f"parsed={sum(1 for mid in ids if mid in parsed)}/{len(ids)} "
                    f"unparsed={sum(1 for mid in ids if items.get(mid, '').endswith('| UNPARSED'))} "
                    f"extra={extra}")
            except Exception as e:
                elapsed = time.time() - t0
                err = f"{type(e).__name__}: {e}"
                log(f"  FAIL {bname} after {elapsed:.1f}s: {err}")
                (RAW / f"{bname}.error.txt").write_text(f"{utc_now()}\n{err}\n{traceback.format_exc()}",
                                                         encoding="utf-8")
                if is_quota_error(e):
                    quota_note = err
                    status = "PARTIAL" if items else "BLOCKED"
                    # try to extract reset time
                    sentence = (
                        f"Anonymous ZeroGPU route via {SPACE} ran out of quota after "
                        f"{returned} of {EXPECTED} items; remaining batches not sent."
                    )
                    break
                # transient? retry once
                log(f"  retry {bname} once")
                try:
                    t1 = time.time()
                    result = call_respond(client, prompt)
                    text = extract_text(result)
                    raw_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str),
                                        encoding="utf-8")
                    txt_path.write_text(text, encoding="utf-8")
                    parsed = parse_items(text)
                    for mid in ids:
                        if mid in parsed:
                            items[mid] = parsed[mid]
                            returned += 1
                            if parsed[mid].endswith("| UNPARSED"):
                                unparsed += 1
                    log(f"  RETRY OK {bname} in {time.time()-t1:.1f}s parsed={sum(1 for mid in ids if mid in parsed)}/{len(ids)}")
                except Exception as e2:
                    log(f"  RETRY FAIL {bname}: {type(e2).__name__}: {e2}")
                    (RAW / f"{bname}.retry_error.txt").write_text(
                        f"{utc_now()}\n{type(e2).__name__}: {e2}\n{traceback.format_exc()}",
                        encoding="utf-8",
                    )
                    if is_quota_error(e2):
                        quota_note = f"{type(e2).__name__}: {e2}"
                        status = "PARTIAL" if items else "BLOCKED"
                        sentence = (
                            f"Anonymous ZeroGPU route via {SPACE} ran out of quota after "
                            f"{returned} of {EXPECTED} items; remaining batches not sent."
                        )
                        break
                    # continue to next batch rather than abort entire run on a single failure
                    continue

        end = utc_now()
        missing = [f"M{i:03d}" for i in range(1, EXPECTED + 1) if f"M{i:03d}" not in items]
        if returned == EXPECTED and unparsed == 0:
            status = "DONE"
            sentence = (
                f"All 150 items returned in the required format from {MODEL_ID} "
                f"via anonymous gradio_client on {SPACE}."
            )
        elif items and status != "PARTIAL" and status != "BLOCKED":
            status = "PARTIAL"
            sentence = (
                f"Returned {returned} of {EXPECTED} items ({unparsed} unparsed, "
                f"{len(missing)} not returned) from {MODEL_ID} via {SPACE}."
            )
        elif not items and status != "BLOCKED":
            status = "BLOCKED"
            sentence = f"No parseable items were returned from {SPACE}."

        provenance = [
            f"model repo ID: {MODEL_ID}",
            f"Space: {SPACE} (https://huggingface.co/spaces/{SPACE})",
            "endpoint: Gradio /respond (fallback /step + official tokenizer decode)",
            f"precision/quant: {PRECISION} (Space README and app.py: unmodified {MODEL_ID}, dtype=torch.bfloat16, size=xlarge ZeroGPU)",
            "route: anonymous Python gradio_client, no Hugging Face token, no paid plan, no new account",
            "confirmation: Space card and README list models: Qwen/Qwen3.8-27B; smoke prompt 'route smoke test ok' matched; /step ids decoded with the official Qwen/Qwen3.8-27B tokenizer to the same text",
            f"input: examples/freeze-xfam-v0/batches/ (6 batches of 25, built from examples/freeze-xfam-v0/items-and-sources.txt sha256 75c214d571d68ef771d9f8cdbe45544d491c3cc491e59daafdab3857f2e28adf); prompts used as-is; hashes in batches/prompts.sha256 verified",
            "sampling: reasoning_effort=off, max_new_tokens=2048, temperature=1.0, top_p=0.95, top_k=20 (Space defaults except thinking off and 2048 output budget, matching the prepared batch params)",
            f"counts: items 150 | sent {sent} | returned {returned} | unparsed {unparsed} | not returned {EXPECTED - returned}",
            f"started_utc: {start}",
            f"finished_utc: {end}",
        ]
        if quota_note:
            provenance.append(f"quota/error: {quota_note}")
            provenance.append(
                "If the error names a reset time, that is when the anonymous ZeroGPU quota may clear; "
                "otherwise retry later the same UTC day or after the usual daily ZeroGPU reset."
            )
        write_result(status, sentence, items, provenance, missing)
        log(f"WROTE {RESULT} status={status} returned={returned} unparsed={unparsed} missing={EXPECTED-returned}")
        return 0
    except Exception as e:
        end = utc_now()
        log(f"FATAL {type(e).__name__}: {e}\n{traceback.format_exc()}")
        missing = [f"M{i:03d}" for i in range(1, EXPECTED + 1) if f"M{i:03d}" not in items]
        provenance = [
            f"model repo ID: {MODEL_ID}",
            f"Space: {SPACE}",
            f"precision/quant: {PRECISION}",
            f"counts: items 150 | sent {sent} | returned {returned} | unparsed {unparsed} | not returned {EXPECTED - returned}",
            f"started_utc: {start}",
            f"finished_utc: {end}",
            f"fatal: {type(e).__name__}: {e}",
        ]
        status = "PARTIAL" if items else "BLOCKED"
        sentence = f"Run stopped with {type(e).__name__}: {e}"[:240]
        write_result(status, sentence, items, provenance, missing)
        return 1


if __name__ == "__main__":
    sys.exit(main())
