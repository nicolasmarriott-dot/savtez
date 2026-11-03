# Contributing to Savtez

Savtez v0.4 fixes the **method**: Rules 0 and 1, the word and message grammar, the generation process and the admission test. The **dictionary** is a work in progress, and anyone may help build it until v1.0.

## How to propose a change

1. Open a GitHub issue in this repository. Use one issue per proposed value, correction or deprecation.
2. In the issue, give:
   - the axis (H, T, E, P, C, A or R) or the head, and the concept in controlled English;
   - why the concept is used often in real messages, with examples;
   - how it answers the axis's one question, overlaps no sibling value and keeps the axis exhaustive;
   - the proposed form, taken from the generated survivor pool (spec section 2). Do not hand-pick a form.
3. The proposal must pass the **admission test** (spec section 7):
   - the value answers its axis's question, overlaps no sibling and keeps the axis exhaustive;
   - the concept is used often in real messages;
   - its form comes from the generated survivor pool;
   - it passes the validator gate and the round-trip test with zero meaning loss.
4. The proposal must pass the **validator gate**: `python3 tools/SAVTEZ-VALIDATOR_v2c.py --gate` ends with `GATE PASSED`, and the Rule 0 typo gates report 0 misdecodes.
5. **The owner decides.** Nicolas Marriott accepts or declines each proposal. An accepted change lands in the next 0.x version.

## Rules that do not change

- The dictionary is append-only. Each version is a prefix of the next, and each version's sha256 is published.
- A retired form or code point is never reused for a different meaning.
- Within a released version, nothing changes.

## Licensing of contributions

Unless you state otherwise in the issue, contributions to `tools/` are under Apache-2.0, and contributions to `spec/` and `data/` are under CC BY 4.0, matching the rest of the repository.
