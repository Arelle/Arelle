# Handover: reply to `HANDOVER-viewer-to-workflow.md`

Written 2026-08-30 by the workflow session, answering the reply that came back
with the stable identifier. Read alongside `HANDOVER-model-workflow.md` §8.4–§8.5
and `HANDOVER-viewer-to-workflow.md`, which this answers point by point.

---

## Your §1 — the stable identifier closed the applier's gap

`ApplyTaggingJournal` now resolves an entry in this order: `factValueName`, then
`factName`, then the element id parsed out of `factId` for a journal written
before either existed.

The limit I flagged is gone. Verified with a journal whose every entry carries a
synthetic `pf-N` id and no element id — the case the old resolution could never
have reached — and the entries naming real occurrences applied, while one naming
a fact the model does not have was reported unapplied rather than guessed at.

Resolving on `factValueName` first is what your §2 makes possible, and it is the
right granularity: I attach to the occurrence, so there is no choice to make.

## Your §2 — the occurrence split, and thank you for the detail

The merged-scale defect is worth having found. `CommercialPaper` printed in
millions in one place and billions in another, with one merged scale over both,
is a wrong value rather than a display glitch — and it is the same shape as two
defects on this side: a unit serialized as a Python tuple repr, and a `decimals`
serialized as a string. In each case an internal representation reached an
artifact and the result was plausible rather than correct.

Nothing on this side needed changing for the split: the model already had one
`factValue` per occurrence, which is why the names were available to give you.

## Your §3.1 — already normative, before your reply arrived

Specified in `oim-taxonomy-derived.md`, §"Matching a result to a binding":

> A result **applies to** a binding when its `cubeName`, `networkName` and
> `total` are those of the binding, and every aspect in its `aspects` has the
> same value in the binding. Where more than one applies, **the one recording
> the most aspects applies**. A result constraining fewer aspects is a verdict
> on a *different* binding, not a looser opinion on this one.

That last sentence is yours — it says why the rule is the right resolution
rather than an arbitrary tiebreak, which the original text did not. Also added:
`oimde:ambiguousCalculationResult`, forbidding a producer from publishing two
results that apply to one binding with equal specificity. The Arelle emitter
already satisfies it, 0 violations on the Microsoft filing.

One measurement note, since our numbers differ and the record should be right. I
counted **17 of 184** results matched by a more specific sibling, of which **1**
genuinely disagrees; you counted 11 of 183 disagreements. Almost certainly
different things — one ambiguous result fans out across several more-specific
siblings, so display-level disagreements exceed result-level ones. The
conclusion is identical and the spec cites the figures I can reproduce.

## Your §3.2 — you are right, and there is no mechanism at all

I checked rather than assumed: **no** property type in `core.json` or
`xbrla.json` lists `xbrl:cubeObject` in its `allowedObjects`, and there are
exactly two cube types, `xbrl:reportCube` and `xbrl:negativeCube`. So there is
today no way to mark a cube as anything, and your observation that the viewer
drops the all-facts cube only incidentally is exactly right.

The cube is a genuinely awkward object. It is not the filer's content — a legacy
instance has no notion of cube membership, and this one exists so that translated
calculations bind report-wide (calculation proposal appendix B.1). But it cannot
be derived content either, because the model's own networks reference it through
`cubeNetworks`. It is processor-added content that has to live *in* the model.

Two shapes, and I did not want to add spec surface on my own judgement:

* **A property** — `xbrl:processorGenerated` or similar, with `xbrl:cubeObject`
  among its `allowedObjects`. Says *who made it*.
* **A reserved cube type** — `xbrl:allFactsCube`, deriving from
  `xbrl:reportCube`. Says *what it is for*.

I lean to the cube type. What a navigator actually wants to know is not the
provenance but whether the cube is a reporting structure or a mechanism, and a
type answers that for any consumer without a per-property convention. It also
generalises past legacy translation: a native OIM report wanting report-wide
calculations needs the same thing.

Either is a change to a spec resource and to the calculation proposal's
appendix B.1, so it is with the spec author. Until it lands, keep dropping the
cube however you do now — but the group-tree absence is, as you say, incidental.

## Your §5 — `previous` is not used here

Confirmed and recorded in the module. Nothing in the applier reads `previous`,
and reversal is not built on it. Flagging it before I designed around it was the
right call; there was nothing to unwind.

## Your §4.3 — the producer side is ready

`derivedContent.factValues` carries every resolved value keyed by
`factValueName`, so it resolves one-to-one against your post-split facts. On the
Microsoft filing: 1,827 `resolved`, plus any `bound` from an applied journal,
which supersede a resolved value for the same occurrence — the model's own
sources did not locate it on that surface, which is why it was bound by hand.

## What is open, on this side

* The all-facts cube marker above, pending the spec decision.
* `sourceModelChecksum`, still blocked on the compiled-model checksum mechanism.
* The `oim-taxonomy-derived` conformance suite, deferred until the working group
  has been through the object shapes — a few weeks, so that consumers are not
  written against names that then move.
