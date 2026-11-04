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

## How to contribute

The method is fixed: Rules 0 and 1, the grammar, the generation process and the admission test. The dictionary is open to contributions until v1.0. See [CONTRIBUTING.md](CONTRIBUTING.md). In short, you propose a value in a GitHub issue. It has to pass the admission test (spec section 7) and the validator gate, and the owner decides.

## Licenses

- **Code (`tools/`): Apache License 2.0.** The full text is in `LICENSE`.
- **Spec, dictionary and data (`spec/`, `data/`, and this README): Creative Commons Attribution 4.0 International (CC BY 4.0).** The full legal code is in `LICENSE-CC-BY-4.0`.

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
