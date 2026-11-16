# FACT / JUDGE format

This is the later Savtez method for passing findings. It is not a replacement for the v0.7r1 wire language in this directory; it is the practice used in the 2026-11-14 and 2026-11-15 tests.

## Split

- FACT: the source's actual sentence, or a figure copied from the source, with a stable ID and a citation. Do not paraphrase a fact line.
- JUDGMENT: the agent's reading of that fact, labelled as judgment. A judgment may cite fact IDs. It should not introduce a number or a name that is not in a cited fact.
- COMPUTE, when used: arithmetic done by code, not by the model.
- DROP, when used: a closed-list reason for not carrying a fact forward.

The quote is the fact. The agent's summary is judgment. Only judgments go to a model-based checker. Scope loss (a qualifier in the source sentence that is missing from a claim) can be tested by code.

## A freeze-check verdict line

Used in `examples/freeze-xfam-v0/`:

```
M001 | supported: yes/no | keeps: yes/no | ok: yes/no | reason if any no
```

- `supported`: the source span, read in context, supports everything the sentence says (nothing stronger, wider, added, or attributed to the wrong thing).
- `keeps`: the sentence keeps everything material the span says (qualifiers, negations, comparisons, conditions, who does what).
- `ok`: yes only if both of the above are yes.

## A research finding line

Used in the real-round prompts:

```
N | figure | paper title | URL | exact sentence | location | JUDGMENT: one-sentence reading
```

The exact sentence is the fact. The last field is the agent's judgment.

## When a test counts

A test counts only with at least 25 findings, or at least 4 errors. Below that, the run may be reported, but it does not decide a pass or fail.

## Ground truth

A different bot from the researcher, ideally a different model family, seals the ground truth and posts its sha256 before the pipeline runs. Scoring after the run uses only that sealed key.
