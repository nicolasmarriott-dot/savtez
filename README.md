# Savtez

- **Author:** Nicolas Marriott
- **Date:** 2026-11-04 (v0.4 released 2026-11-03)
- **Status:** v0.7r1 specification and dictionary frozen; v0.7 validator in progress. Work in progress: dictionary open to contributions until v1.0

This repository is a dated public record of Savtez (v0.4, and v0.7r1 from 2026-11-04) and an open work in progress. The full history is in [RECORD.md](RECORD.md). Savtez is not a standard, and nobody has adopted it.

## Purpose

Savtez is a compact, exact language for messages between AI agents and for their shared memory. Each word is built from parts. Each part answers one fixed question about a head concept such as a claim, a source, a task or a figure. The questions are handling, task state, evidence, derivation, corroboration, absence and relation. This lets an agent say "claim verified against a primary source, single-origin" in one checked word instead of a sentence that could be paraphrased or misread. The goal is to free context by packing exact meaning into few units, and to remove misreads and clarification rounds. Humans keep English. Any Savtez message translates back to English deterministically.

## Rule 0: no misreading

The language must be impossible to misunderstand or decode wrongly. This outranks brevity. In practice:

- each meaning has one form;
- no part resembles a word, acronym or slang term in any major language;
- the alphabet has no confusable characters;
- the grammar rejects every invalid combination, so a damaged word fails loudly instead of quietly decoding to something else;
- decoding is done by the deterministic validator, never by a model's guess.

The misdecode rate in testing must be zero.

## Rule 1: pure logic

Every rule follows from logic. Each axis asks exactly one question. Its values are mutually exclusive (one per word) and exhaustive (every case has a value). The following rules come from that:

- slot order is fixed (one meaning, one spelling);
- there is no "not", because it would create synonyms;
- relations take 0 or 2 sides, because one side is incomplete;
- the seven axes are split so that each asks one question: H handling, T task state, E evidence, P derivation, C corroboration, A absence, R relation.

## Auditability

- **Public dictionary.** The dictionary is public, versioned and append-only. Each version's sha256 is published. A retired form or code point is never reused for a different meaning.
- **Deterministic translation to English.** The validator translates every message back to English. A model's opinion never decides the meaning.
- **No free choices.** Every degree of freedom either carries a dictionary meaning or is normalized away: one symbol per part, no variants, fixed order, normalized whitespace. Non-canonical input is rejected.
- **No hidden channels.** With no free choices, there is nowhere to hide a covert side-channel such as the glyph-variant scheme documented by Beltoft et al. 2026. Free-text detail fields stay limited to controlled English and figures, and every message is logged append-only.

## Example

`^zbhdxzwfzk` means **claim, verified against a primary source, single-origin (no independent corroboration)**.

| Part | Slot | Meaning | Code point |
|---|---|---|---|
| `^` | sigil | marks a Savtez word | U+E800 |
| `zbh` | E evidence | verified against a primary source | U+E100 |
| `dxz` | C corroboration | single-origin, no independent corroboration | U+F200 |
| `wfz` | head | claim | U+E000 |
| `k` | check | check character over the parts | (U+E902 in the canonical form) |

```sh
$ python3 tools/SAVTEZ-VALIDATOR_v2c.py '^zbhdxzwfzk'
VALID | ^zbhdxzwfzk | claim | E evidence: verified against a primary source; C corroboration: single-origin, no independent corroboration | canonical U+E800 U+E100 U+F200 U+E000 U+E902 | ASCII ^zbhdxzwfzk | legacy savpevkef
```

If you change any one character, or swap two adjacent ones, the word is rejected.

## Repository layout

| Path | Contents | License |
|---|---|---|
| `spec/SAVTEZ-SPEC_v0.7r1.txt` | language specification, v0.7r1 (current; frozen 2026-11-04) | CC BY 4.0 |
| `spec/SAVTEZ-DICT_v0.7.txt` | v0.7 dictionary: every part, its form and code point, and the 188-form inventory | CC BY 4.0 |
| `spec/SAVTEZ-PREDICATES_v0.7.txt` | closed list of action predicates for `do=` | CC BY 4.0 |
| `RECORD.md` | the complete record of the project to date | CC BY 4.0 |
| `spec/SAVTEZ-SPEC_v0.4.txt` | language specification, v0.4 | CC BY 4.0 |
| `spec/SAVTEZ-DICT.txt` | v0.4 dictionary and change log (to v0.5) | CC BY 4.0 |
| `tools/SAVTEZ-VALIDATOR_v2c.py` | deterministic validator and decoder (Python 3, standard library only) | Apache-2.0 |
| `tools/SAVTEZ-GENERATE_v0.3_r3.py` | generator for the ASCII forms | Apache-2.0 |
| `data/SAVTEZ-CODEPOINTS_v2c.txt` | code point table: concept, axis, ASCII form | CC BY 4.0 |
| `data/SAVTEZ-GATE_v2c.txt` | recorded validator gate run | CC BY 4.0 |
| `data/SAVTEZ-GENERATED-FORMS_v0.3_r3.txt` | generator output: candidate forms and screening tables | CC BY 4.0 |
| `data/SAVTEZ-LISTS_v2.txt` | public lists and data sources the generator used | CC BY 4.0 |
| `spec/FACT-JUDGE.md` | later method: the source sentence is the FACT; the agent's reading is JUDGMENT | CC BY 4.0 |
| `spec/tests/` | test specifications for the FACT/JUDGE work (2026-11-14) | CC BY 4.0 |
| `tools/freeze-xfam-v0/` | scripts to batch, run and score the freeze cross-family example | Apache-2.0 |
| `tools/pointer/` | scripts used in the pointer-chain, freeze, cutter and relay tests | Apache-2.0 |
| `tools/cardcheck/` | deterministic citation checker (v0.2) | Apache-2.0 |
| `examples/freeze-xfam-v0/` | worked example: 150 items, Qwen verdicts, score, and how to rescore | CC BY 4.0 |
| `examples/cardcheck/` | calibration claims and scores for the citation checker | CC BY 4.0 |
| `examples/pointer/` | recorded results of the 2026-11-14 pointer-chain and relay tests | CC BY 4.0 |
| `examples/real-round/` | a FACT/JUDGE research prompt and two recorded rounds | CC BY 4.0 |
| `SHA256SUMS` | sha256 of every other file in the repository | n/a |

## How to run the validator

You need Python 3. The validator has no third-party dependencies.

```sh
python3 tools/SAVTEZ-VALIDATOR_v2c.py --gate            # full gate: gate cases, legacy gate, edge cases, Rule 0 typo gate
python3 tools/SAVTEZ-VALIDATOR_v2c.py --gate --quick    # faster, sampled typo gate
python3 tools/SAVTEZ-VALIDATOR_v2c.py --table           # code point table
python3 tools/SAVTEZ-VALIDATOR_v2c.py WORD              # validate and decode one word
python3 tools/SAVTEZ-VALIDATOR_v2c.py -f message.txt    # validate and decode a message
python3 tools/SAVTEZ-VALIDATOR_v2c.py --hash -f message.txt   # 8-hex body hash for critical messages
```

A passing gate ends with `SUMMARY | ... | GATE PASSED`. The exit code is 0 on a pass and 2 on a failure. For a single word or message, the exit code is 0 for VALID and 1 for REJECT.

The validator in `tools/` is for v0.4. The v0.7 validator is being built and will be added with its test vectors.

Note: validator v2c decodes the v0.4 words, but it still expects the message header `§L0.3`. A header that says `§L0.4` is rejected until the validator's version table is updated.

You can check the files against the checksums with `sha256sum -c SHA256SUMS`.

The generator needs `wordfreq`, `tiktoken` and `tokenizers`, plus local copies of the word lists, tokenizer files and corpora listed in `data/SAVTEZ-LISTS_v2.txt`. None of these are included here. Put them under `external/`, or set `SAVTEZ_WORDLISTS`, `SAVTEZ_TOKENIZERS` and `SAVTEZ_CORPORA`. The generator also reads its acronym list from `tools/SAVTEZ-PROPOSE_v0.3.py`, which is not included in this release.


## FACT / JUDGE

Later work in this repository uses a simpler passing rule than the compact wire language above. The two sit side by side. The v0.7r1 language is the formal message format. FACT/JUDGE is the method for passing research findings without the facts drifting. The note in `spec/FACT-JUDGE.md` and the test specifications in `spec/tests/` record the method.

- FACT: a verbatim sentence from a named source, or a figure copied from that source, with a stable ID. It is not a paraphrase.
- JUDGMENT: the agent's reading of what that fact shows, labelled as judgment. This is the only part a model-based checker is asked to score.
- A test of the method counts only if it produces at least 25 findings, or at least 4 errors.
- Ground truth is sealed, and its sha256 posted, by a different bot from the one that researched the round, ideally from a different model family, before the pipeline runs. Thresholds and pass rules do not change after results are in.

A research finding line looks like this:

```
N | figure | paper title | URL | exact sentence | location | JUDGMENT: one-sentence reading
```

The exact sentence is the fact. The last field is the agent's judgment. An example prompt is in `examples/real-round/TO-AI_grok-round_2026-11-14.txt`.

## The freeze-xfam-v0 worked example

On 2026-11-14, 150 sentences were judged against short source quotations. Some sentences were faithful to the quoted span; others contained one planted change of meaning. Checker A produced 150 verdicts in `examples/freeze-xfam-v0/freeze-judgment-20261114.txt`.

The answer key used for scoring was:

- PLANTED = the 124 items Checker A marked `ok: no`, plus item M009 (125 items). The recorded result calls M009 arguably not an error; the key still counts it as planted.
- CLEAN = the other 25 items.

This key was derived from Checker A's verdicts, with M009 added by the scoring rule, and the counts (125 planted, 25 clean) were checked before scoring. It was not a separately posted ground-truth file sealed before Qwen ran.

On 2026-11-15, Qwen/Qwen3.8-27B (bf16) judged the same 150 items through the public Hugging Face Space `bottlecapai/Qwen3.8-27B-reference`, called anonymously with Python `gradio_client` (no token, no paid plan). Sampling: `reasoning_effort=off`, `max_new_tokens=2048`, `temperature=1.0`, `top_p=0.95`, `top_k=20`.

Result: Qwen caught 121 of 125 planted items, and raised 0 false alarms on 25 clean items. It missed M046, M066, M124 and M127. Checker A caught those four; Qwen caught M009. The two checkers shared no misses.

Original hashes of the delivered files, before path or name substitution and before the source quotations were trimmed for this repository:

- `freeze-judgment-20261114.txt`: 11816 bytes, sha256 `6804a5cd5628dbfdc8d8cb85359d4898217b349c6a3e43be7d6ec1293f6479aa` (byte-identical here)
- `result.txt`: 15903 bytes, sha256 `e6856bda3daed69f7d980388e8df30b838d1009dbd94d7799f3f6aff26ed6e2c`
- `score-20261115b.txt`: 1179 bytes, sha256 `919f89ffded855d6ea1735618d24623b313807307985840a228478fc54ffca76`
- `items-and-sources.txt` (original name `task-20261114e.txt`): sha256 `75c214d571d68ef771d9f8cdbe45544d491c3cc491e59daafdab3857f2e28adf`

The copies of `result.txt` and `score-20261115b.txt` here have internal machine paths and internal checker names replaced, so their sha256 values differ; see `SHA256SUMS`. The 150 verdict lines in `result.txt` are unchanged. `items-and-sources.txt` and the batch prompts have had surrounding source paragraphs removed (see below), so they also differ. A short record is in `examples/freeze-xfam-v0/ORIGINAL-HASHES.txt`.

### How to rescore the published run

```sh
python3 tools/freeze-xfam-v0/score.py \
  examples/freeze-xfam-v0/freeze-judgment-20261114.txt \
  examples/freeze-xfam-v0/result.txt
```

This should report: caught 121 of 125 planted, 0 false alarms on 25 clean, misses M046, M066, M124, M127. The scorer reads only the verdict lines. It does not depend on the trimmed source text.

### How to rerun the model

1. The 150 items, with their quoted source spans, are in `examples/freeze-xfam-v0/items-and-sources.txt`. Batches of 25 are in `examples/freeze-xfam-v0/batches/`.
2. `tools/freeze-xfam-v0/run.py` calls the same Space anonymously. It refuses to run if a Hugging Face token is present in the environment.
3. A rerun may not match the published lines token-for-token: the original sampling used temperature 1.0, and the packaged prompts no longer include the surrounding source paragraphs that were sent on 2026-11-15. The published `result.txt` is the record of that run.
4. The quoted spans are short excerpts from Philip Kiely, *Inference Engineering* (Baseten Books, 2026). See `examples/freeze-xfam-v0/SOURCE.txt`. Surrounding paragraphs from the book are not in this repository.

## How to run the later tools

The freeze scorer uses only the Python standard library. The optional model runner needs `gradio_client`, `huggingface_hub` and `tokenizers`, and it will not start if a Hugging Face token is set.

```sh
python3 tools/freeze-xfam-v0/score.py \
  examples/freeze-xfam-v0/freeze-judgment-20261114.txt \
  examples/freeze-xfam-v0/result.txt
python3 tools/freeze-xfam-v0/build_batches.py
# python3 tools/freeze-xfam-v0/run.py    # optional; calls the public Space
```

`tools/pointer/` and `tools/cardcheck/checker_v0.2.py` support the earlier tests whose specifications are in `spec/tests/` and whose recorded results are under `examples/`. The pointer-chain tests also used passages from *Inference Engineering*; that passage corpus is not included here, so those tests cannot be replayed from this repository alone.

## How to contribute

The method is fixed: Rules 0 and 1, the grammar, the generation process and the admission test. The dictionary is open to contributions until v1.0. See [CONTRIBUTING.md](CONTRIBUTING.md). In short, you propose a value in a GitHub issue. It has to pass the admission test (spec section 7) and the validator gate, and the owner decides.

## Licenses

- **Code (`tools/`): Apache License 2.0.** The full text is in `LICENSE`.
- **Spec, dictionary, data and examples (`spec/`, `data/`, `examples/`, and this README): Creative Commons Attribution 4.0 International (CC BY 4.0).** The full legal code is in `LICENSE-CC-BY-4.0`.

When you reuse the spec, dictionary or data, credit "Nicolas Marriott, Savtez v0.7r1, 2026-11-04" (or the version you used).

## Prior art and credit

Savtez builds on the following work and credits it. Evidence tagging is not new, because HCAN and thoughtml already do it. What Savtez contributes is the combination: agent-to-agent messaging, typed slots including task state, an append-only public dictionary, generated forms, and symbols meant to be trained as single tokens.

- **FIPA-ACL.** Foundation for Intelligent Physical Agents, *FIPA Communicative Act Library Specification* (SC00037) and *FIPA ACL Message Structure Specification* (SC00061). All 8 Savtez message acts come from the FIPA library.
  http://www.fipa.org/specs/fipa00037/SC00037J.html
  http://www.fipa.org/specs/fipa00061/SC00061G.html
- **W3C PROV-O.** *PROV-O: The PROV Ontology*, W3C Recommendation. Savtez's derivation values and deltas map to it.
  https://www.w3.org/TR/prov-o/
- **A2A.** *Agent2Agent (A2A) Protocol*, specification repository. The Savtez task-state axis maps to A2A TaskState.
  https://github.com/a2aproject/A2A
- **HCAN.** Hearth & Code, *HCAN: a proposed human-agent communication notation*. It carries source, evidence, inference and unknown markers.
  https://hearthandcode.dev/hcan/
- **thoughtml.** *ThoughtML: a plain-text language for reasoning you can check*. It tags values as measured, estimated or assumed.
  https://fatin-ishraq.github.io/ThoughtML/
- **Beltoft et al. 2026.** S. L. Beltoft, W. Brach, F. Torrielli, J. Nielsen, A. B. Pirchert, F. Tonini, P. Schneider-Kamp, L. G. Poech, *Emergent Languages in Populations of Language Model Agents: From Token Efficiency to Oversight Evasion*, arXiv:2605.31170, 2026. The auditability principle is based on this paper.
  https://arxiv.org/abs/2605.31170
