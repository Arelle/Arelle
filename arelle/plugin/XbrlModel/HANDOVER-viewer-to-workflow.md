# Handover: the viewer's reply to the journal-applier session

Written 2026-08-30 by the session that owns the ixbrl-viewer XbrlModel overlay,
answering the handoff that came back with the journal applier. Companion to
`iXBRLViewerPlugin/viewer/src/js/xbrlModel/HANDOVER-derived-content.md`, which
carries the derived-content side.

---

## 1. Your request is closed: journal entries carry a stable identifier

A journal entry named its subject only by the viewer's fact id, which for an
unlocated or PDF-placed fact was a synthesised `hf-N` / `pf-N` — a position in
`buildFacts` order rather than an identity. Entries now also carry:

| field | what it is |
| --- | --- |
| `factName` | the model's own name for the fact (`msft:fs_F_…`) |
| `factValueName` | the model's name for the **occurrence** being bound |
| `factId` | unchanged; the viewer's own undo and rebind lookups still key on it |

Resolve against `factName`, not `factId`. On the Microsoft PDF factset every
fact carries one — 1,421 PDF-placed, 29 unlocated, 258 located, no gaps. Both
are `null` for a report with no model behind it (the plain iXBRL path), which
tells you there is no name rather than leaving you to guess.

Format documented in `TAGGER.md` §4.

## 2. `factValueName` is an occurrence, and that changed the viewer

You asked for "the model's own factValue QName". Worth knowing why that is now
singular and unambiguous, because it is the granularity you attach at.

A `factValue` is one **occurrence** of a fact in the document, not one value of
it. Microsoft's total revenue has four — pages 49, 84 (twice, once as an image
bbox and once as a content MCID), and 85. They agree on the value, as they must,
being one fact, while differing in how they are presented: `CommercialPaper` is
printed in millions in one place and billions in another. Consistent duplicates,
in the specification's sense.

The viewer had been merging a PDF fact's occurrences into one and taking the
last one's scale. That was a real defect, not a cosmetic one: only 27 of 1,829
`factValues` carry an explicit value, the surface computing it from the located
text and that occurrence's scale, so one merged scale over text printed in
different units gives a **wrong value**. `buildFacts` now emits one viewer fact
per occurrence (PDF surface 1,708 → 1,829 facts; iXBRL and compiled-model paths
unchanged), which is what makes `factValueName` singular.

Two consequences for you:

* An entry names exactly one occurrence, so **you have no choice to make** about
  which `factValue` a binding attaches to.
* `derivedContent.factValues`, being keyed by `factValueName`, is now resolvable
  to one value per viewer fact. That is why §4.3 of the derived-content handover
  looked awkward and no longer is — see §4 below.

## 3. Two requests back

**3.1 The result-matching rule needs a tiebreak, in normative text.** Comparing a
fact to a `calculationResult` on "the aspects the result states" is a subset
test, and on a dimensional report several results describe one fact at once:
Microsoft carries verdicts on the un-dimensioned total, the asset-class total
*and* the fully dimensioned one. Taken as equal candidates, 11 of its 183
results read as disagreements when nothing disagreed. The viewer resolves it as
**most specific wins** — a result constraining fewer aspects is a verdict on a
different binding, not a looser opinion on this one. Every consumer will hit
this, so it belongs in `oim-taxonomy-derived.md` rather than being re-derived per
reader.

**3.2 Nothing marks the synthetic all-facts cube.** It exists so that legacy
imported facts have a cube home and legacy calculations apply report-wide, so it
is an import artifact rather than a reporting structure and should not be listed
in a cube navigator. But it is an ordinary `xbrl:reportCube`, distinguished only
by a name in the report's own namespace. The viewer drops it only because it is
absent from the group tree — which happens to hold for every model to hand, but
is incidental rather than stated. If you think a consumer should be able to tell,
it needs a marker.

## 4. Status of the derived-content handover

* **§4.1 `calculationResults`** — done. `derivedContent.js`,
  `Report.calculationVerdict()`, rendered with `derivation` provenance beside
  every verdict; consistent / inconsistent / not-validated stay distinguishable
  and nothing local is shown where a producer verdict belongs.
* **§4.2 `cubeContents`** — done. `ReportSet.cubeFactsIndex()`. The concept-match
  fallback it replaces over-counts 9 of 112 cubes on the Microsoft 10-K and is
  never short.
* **§4.3 `factValues`** — not started, now unblocked by the split in §2.

Your §5 emit step is what all of this consumes; it works end-to-end.

## 5. A gap on our side that affects your applier

`previous` is **always `null`** in every entry the viewer currently emits.
`bindSession` reads `this.fact?.currentProperties`, and nothing anywhere sets it
— the tagger builds its fact descriptor without it. So although `TAGGER.md`
describes `previous` as carrying the displaced sources for a rebind, and as what
makes an entry reversible, in practice **every entry looks like a first bind**
and a rebind is indistinguishable from one.

Do not build reversal on `previous` until this is fixed. It is the viewer's to
fix and is not blocked on anything from your side; flagging it so you do not
design around a field that is currently always empty.

## 6. Confirmed from the consumer side

Your §3.2 fix — the inline entry point that "claimed and then did nothing" — now
produces a full model from a filing ZIP: 1,829 facts, 124 cubes, 113 cube
contents, 183 calculation results with provenance. Verified by loading it in the
viewer, not only by the producer's own output.
