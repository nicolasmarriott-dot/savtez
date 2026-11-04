# Savtez: The Complete Record

Nov 4, 2026 · @Nicolas Marriott

Savtez is Nick Marriott's exact, compact language for AI agents to message each other and keep shared records. Started Nov 2, 2026; v0.7r1 frozen Nov 4; not yet published beyond the v0.4 repo.

## What it is and why

AI agents talk to each other in English, which is long, vague and easy to misread. Every misread costs a clarification round, a wrong action or a wrong record. Savtez replaces that with messages that cannot be misread, and that a validator with no AI inside turns back into English for any human.

Nick's reasons, in his terms:

- **No misreading.** Rule 0: impossible to misread or decode wrongly; it outranks brevity. Rule 1: each axis asks one question, with exclusive, exhaustive values.
- **Free memory, not just tokens.** Everything an agent holds sits in GPU memory for the whole session; memory often caps how many sessions a data centre serves.
- **Built for all AI.** Designed on the assumption every AI developer eventually builds it in natively.
- **More observable AI, not less.** Agents talking in Savtez are auditable by anyone, through the validator's English translation.
- **Open but credited.** Apache 2.0 with Nick named as originator; governance moves to an independent body before 1.0.
- **Honest about results.** Its efficiency claim is tested in a pre-registered pilot, and a negative result is published like a positive one.
- **Standard:** no rush; keep improving it until it is a work of art.

## Timeline

Three days, newest first (times PT).

| When | Milestone |
| --- | --- |
| Nov 4, 05:50 | Erratum E1 from the 336-case test suite: spec v0.7r1 |
| Nov 4, 05:30 | v0.7 dictionary and two independent validators started |
| Nov 4, 05:26 | **v0.7 frozen** after 7 hostile review rounds |
| Nov 4, 04:56 | Token bench 3: 27-32% fewer tokens than structured English |
| Nov 4, 00:10 | Status map: three-layer vision (communication, shared knowledge, coordination) |
| Nov 3, 22:40 | Nick: the hash line stays mandatory in every message |
| Nov 3, evening | Ambiguity hunt + clean-room second validator: 0 disagreements on \~274,000 inputs; rulings A1-A13; GBNF grammar passes; v0.7 draft 1 |
| Nov 3, afternoon | v0.6r1 rebuilt from v0.4 + logged rulings; SE-1 (structured-English control arm) written |
| Nov 3, mid-day | Safety side path: approval lock v0.8 (frozen at draft 10), consumer and everyday profiles; then parked: "finish the language first" |
| Nov 3, morning | Pilot pre-registered (20 messages, answer key, sealed seeded errors); legal package drafted (Apache 2.0, NOTICE, trademarks, governance) |
| Nov 3, 01:21 | **v0.4 published** on GitHub (nicolasmarriott-dot/savtez, commit ddc6e0d) |
| Nov 3, early | v0.5: 188-form pool, check character, new axes (visibility, mutability, lifecycle, blocker, urgency, scope, standing) |
| Nov 2 | Idea starts as AGENT-LANG; named Savtez (sav + tez, "a verified statement"); Rule 0 set; forms to be generated, not hand-picked; prior-art scan |

## How the language works

A Savtez message is a few short lines a validator can check mechanically and translate to English exactly.

```text
$L0.7 ^yzdxhgz @msg:relay:7
+ ^xjhzbhpzxdxzwfzb | @source:dodig-2025-137
#3695a800
```

That example (from bench 3) reads: an *inform* message under the sender's own authority; one new line, asserted by the sender: a claim, verified, quoted, single-origin, citing a named source; then the message hash.

- **Words.** `^` + 3-letter parts + 1 check letter. Parts are generated from a 17-letter alphabet, screened so no part means anything in a human language. The check letter catches every single typo (254 million edits tested on v0.6r1, 0 accepted).
- **Slots.** Each word answers fixed questions in a fixed order: who asserts it; visibility; mutability; task lifecycle, blocker, urgency; coverage; source tier; evidence; derivation; corroboration; scope; absence; test outcome and timing; relation type; then the head (claim, source, task, figure, statement made, act done, relation, gap, log entry, test).
- **Messages.** A header (version, act and standing, message ID), body lines that add (`+`), replace (`~`) or retract (`!`) records, typed references (`@actor:`, `@file:f1`, `@msg:sender:seq:line`), keyed fields (`fig=`, `due=`, `checker=`, `prob=`…), one free-text `note=`, and a mandatory hash line.
- **Evidence.** A verified claim must cite a verified primary source and an excerpt found verbatim in it (64 bytes or more), and name who judged it. Sources are verified by signature or signed retrieval, against an owner-signed trust list.
- **The validator.** Deterministic code, no AI. It checks form only, and attributes every judgment of meaning to a named checker. Damaged or invalid input is rejected, never repaired or guessed.
- **No certainty words.** "Probably" and its kin are banned; certainty is a number in `prob=`.

## Versions

Each version's rules are frozen once released; a message decodes only against the version in its header.

| Version | Date | What changed | Status |
| --- | --- | --- | --- |
| v0.7r1 | Nov 4 | Erratum E1: file-limit wording made consistent | Canonical, unpublished |
| v0.7 | Nov 4 | ASCII-only wire with `$L` prefix; asserter inside the word; one-word header; keyed ref lists; file handles + one manifest hash; cross-message line refs; mandatory `checker=` for judgments; excerpt floor and validation limits; signed sources and trust lists | Frozen after 7 review rounds |
| v0.6r1 | Nov 3 | Rebuilt by Claude from v0.4 + rulings when the bot box was lost; 79 parts, 57,072 valid words; gate PASS | Baseline of the pre-registered pilot |
| v0.6 | Nov 3 | Bots' draft; rulings partly lost with the old box | Superseded |
| v0.5 | Nov 3 | 188-form generated pool; check character (mod 1009 + parity in the PUA form); new axes: visibility, mutability, lifecycle, blocker, urgency, scope; standing in the header, asserter per line | Superseded |
| v0.4 | Nov 3 | First public release; generated forms, sigil + check, 7-slot axis fix | Public on GitHub |
| v0.3-draft | Nov 2 | Slot model, two forms (PUA symbol + letters), FIPA message acts, deltas, @refs; name Savtez chosen | Superseded |
| v0.2 | Nov 2 | AGENT-LANG: pronounceable 3-letter parts (kef = claim, sav = verified…); admission by token savings | Retired: forms no longer pronounceable or hand-picked |

Two shifts mattered most. On Nov 2, Nick ruled the language only needs to be understood by AI, so forms became generated and meaning-free instead of pronounceable. On Nov 3-4, the reviews moved every judgment of meaning out of the validator and onto a named checker.

## Testing and measurement

Every claim about Savtez is either mechanically tested or fixed in a pre-registration before any run.

| Test | Result |
| --- | --- |
| v0.6r1 gate (validator `--gate --full`) | 142 cases PASS; every word decodes identically in both forms; 254M single-typo edits, 0 accepted; reproduced on the bot box |
| Second implementation (clean-room, v0.6r1) | 0 disagreements on \~274,000 inputs; 13 ambiguity rulings (A1-A13) |
| Double typos (v0.6r1) | 0.0006% slip through (69 of 11.5M sampled), mostly 4 form pairs; fixable by reassigning forms |
| Constrained-decoding grammar | 0 of 57,072 valid words rejected; 0 of 444,538 typos accepted; 38/38 gate messages accepted |
| SE-1 | 6,076/6,076 exact round trips; 3,176 malformed inputs all rejected |
| Token benches 1-3 (7 tokenizers) | v0.6r1: 16-22% fewer tokens than SE-1; v0.7 encoding: 27-32% fewer, hash kept. PUA form costs more, so ASCII is the wire form |
| Single-token scan | No meaning-free 1-token pieces exist in today's tokenizers; 2 tokens per part is the floor until labs add native tokens |
| v0.7 conformance suite | 336 cases; found 1 spec conflict (erratum E1) |

**The pilot (pre-registered, not yet run).** 20 real bot messages, each written three ways: plain English, structured English (generated mechanically by SE-1) and Savtez. Fresh AI sessions that never saw the sources encode and blind-decode them. Savtez must use at least 20% fewer tokens than plain English and 10% fewer than structured English, dictionary included, with zero meaning loss. Otherwise its efficiency claim is withdrawn and the negative result is published. The answer key is 453 script-extracted tokens plus 156 closed questions answered unanimously by three AI families; a sealed file of seeded errors checks that decoders catch damage. The pre-registration will move from v0.6r1 to v0.7 with Nick's approval.

A method lesson from building the key: two honest AIs writing free-form field lists agreed on only 5% of meanings, while closed questions answered blind by three AI families agreed 95%.

## Safety track (parked)

The approval lock is a design where no AI agent can take a real-world action without an exact human signature and a public trace. Nick parked it on Nov 3 to finish the language first; it may be the bigger contribution, so it is kept separable from Savtez.

**Core property (v0.8, frozen at draft 10):** every locked action traces to one exact human signature, or to one still-valid, bounded, human-signed permission. It is publicly committed before it runs. No AI holds credentials. The gate contains no AI and fails closed. Changes are allowed only for a demonstrated bypass.

How it works:

- The human signs the exact final payload on hardware (P-256 now, post-quantum alongside), after an English round trip by two independent translators.
- A shared nonce and revocation store stops replays.
- Each locked action is publicly counted before it runs: a \~50-byte record (hash, action class, time, count). The content is sealed for an independent auditor, whose demands go to the public log.

| Profile | Status | What it adds |
| --- | --- | --- |
| Consumer, draft 2 | Proposed | Standing permissions (bounded, listed recipients, 30-day maximum, never for first contact, deletion, publication or large payments); locale packs; per-person shards; recovery; accessibility |
| Everyday, draft 1 | Proposed | No noticeable delay (under 150 ms): 2 of 3 independent witnesses promise publication within 60 seconds; approvals use the phone's existing payment or passkey sheet |

Open decisions for Nick there: P-256-only consumer approvals with a hard migration date, and the interpreter tick length.

Positioning: Savtez and the lock raise the cost of misuse for systems below a dangerous capability threshold. They sit below compute governance, training controls and goal verification and replace none of them. Savtez is never a reasoning language. On Nov 4 Nick added the aim that the safety side should also protect AI and people from powerful actors misusing it: public traces, no single owner, no override key.

## Other branches

Five side tracks grew from the core; all wait until the core language is complete and tested.

| Branch | Where it stands | File |
| --- | --- | --- |
| **Shared knowledge (layer 2)** | Concept: records that correct themselves across agents (retractions cascade, conflicts branch instead of being rejected, a state root two implementations must agree on). First demo idea: a real FraudNet evidence file with a real correction | `SAVTEZ-BRAINSTORM-1.txt` |
| **Emotions module** (Nick's idea) | Draft 1: appraisal axes plus one attack round. The same exact grammar describing human feelings, with the person as the authority on their own feelings and privacy built in | `SAVTEZ-AFFECT-AXES_draft1.txt` |
| **AI efficiency map** | Much of AI's spend is re-discovering its own environment; replace repeated probabilistic work with reusable deterministic computation. Mostly unmeasured | `AI-EFFICIENCY-MAP_code-agents_ChatGPT.txt` |
| **Stage 2 experiment** | Preregistration v1.3: three coding agents on 60 public bugs, structured English vs Savtez; token-only claim with fixed loss rules. Needs the pilot passed and a self-hosted GPU | `STAGE2-PREREG_coding-agents_v1.3.txt` |
| **Native-token track** | ASCII is the normative wire; labs could map parts to dedicated tokens through a manifest. Token savings beyond ASCII are a hypothesis until measured. Best adoption idea: a reference tokenizer + LoRA for one open model (needs GPUs) | v0.7 spec, section 16 |

**Adoption and licence.** The route is an A2A extension: a Savtez payload carried as a raw Part with media type `application/vnd.savtez`, via an experimental-ext repo with a maintainer sponsor. Nothing is posted without Nick's word. The licence package is Apache 2.0, a NOTICE naming Nick as originator, a trademark policy, DCO contributions and a governance hand-off before 1.0; lawyer review is recommended before publishing.

**Prior art.** Evidence tagging exists elsewhere (HCAN, thoughtml), as do compact agent formats (CodeAgents, ADOL, CLowl, PCM, Slipcore). Savtez's claim is the combination: exact agent-to-agent typing, evidence and task state in one word, an append-only public dictionary, a deterministic validator, and a public falsifiable test.

## Where things stand

The core language is frozen; the remaining work proves it in code and in the pilot.

1. **Dictionary** (in progress): the new parts v0.7 needs.
2. **Two validators**: a reference build and a blind build, both run on the 336-case suite and against each other until they agree on everything.
3. **Grammar file and byte-level test vectors** for v0.7.
4. **Pilot**: run on v0.7 after Nick approves the change from v0.6r1.
5. **Publication** on Nick's word, after lawyer review.
6. **Later**: Stage 2 experiment, shared-knowledge layer, emotions module, safety track.

### Open decisions

- [ ] Nick: move the pilot pre-registration from v0.6r1 to v0.7.
- [ ] Nick: publication timing and lawyer review.
- [ ] Nick: consumer-lock choices (P-256 migration date, tick length) when the safety track resumes.
- [ ] v0.8 candidates: a "rendition of" relation; naming a non-sender asserter; a "lookalike, distinct entity" relation for fraud work.

### Key files (Project, `claude/`)

| What | File |
| --- | --- |
| Canonical spec | `SAVTEZ-SPEC_v0.7r1.txt` |
| Pilot baseline spec, validator, dictionary | `SAVTEZ-SPEC_v0.6r1.txt`, `SAVTEZ-VALIDATOR_v0.6r1.py.txt`, `SAVTEZ-DICT_v0.6r1.txt` |
| Latest handoff | `HANDOFF-2026-11-04-Savtez-v0.7.txt` |
| Tonight's summary | [Savtez v0.7: Night of Nov 3-4, 2026](https://claude.ai/artifact/HJbxFwo7EjW3D4BkzXNan1) |
| Pilot | `PILOT-PREREGISTRATION.md`, `PILOT-20-MESSAGES.txt`, `PILOT-SCORING-SET.txt` |
| Structured-English arm | `SE1_v0.1r2.py.txt` |
| Grammar | `savtez-v0.6r1.gbnf.txt` |
| Approval lock and profiles | `SAVTEZ-SPEC_v0.8-approval-lock.txt`, `SAVTEZ-PROFILE_consumer_draft2.txt`, `SAVTEZ-PROFILE_everyday_draft1.txt`, `SAFETY.md` |
| Legal package | `SAVTEZ-LEGAL-PACKAGE.txt` |
| Dictionary history (v0.2-v0.5) | `SAVTEZ-DICT.txt` |
| Working methods | `ENGRAM.txt` (section 16) |

Public repo: [github.com/nicolasmarriott-dot/savtez](https://github.com/nicolasmarriott-dot/savtez) (v0.4).
