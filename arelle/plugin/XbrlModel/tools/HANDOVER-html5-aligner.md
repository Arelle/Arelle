# Handover: an HTML5 target for the fact aligner

For the session that owns `tools/alignFactsToSurface.py`.

`alignFactsToSurface` maps facts from a tagged inline document onto a *second*
rendering of the same report, emitting locators for the second one. Today the
second rendering is always a PDF. The ask is to add HTML5 as a second target,
emitting `xbrlx:htmlElementPointer` instead of `pdfPage`/`pdfMcid`.

This note carries what the tagger session established, so the alignment work does
not have to rediscover it. Written 2026-08-21.

---

## 1. Why this is wanted

W3C retired XHTML 1.1 in 2018. Inline XBRL 1.1 is built on it, so a toolchain
that can only address XHTML is tied to a substrate the web has moved on from.
The demonstration target is a published HTML5 annual report with **no XBRL at
all** — the aligner places the filing's facts onto it, and the viewer lets a
human confirm and correct.

It is also the evidence for the `xbrlElementPointer` proposal, because such a
document cannot be addressed any other way. Measured on Microsoft's public
annual report: **42 elements carry an `id`, out of 8,383 — 0.50%**, and all 42
are navigation anchors (`home`, `shareholder-letter`, `financial-review`).
Not one figure in its 66 tables is reachable by `xbrl:htmlElementId`.

## 2. What splits cleanly

| part | status |
|---|---|
| token stream from the target HTML5 document | new — §3 |
| word index mapping tokens back to elements | new — analogous to `_build_mcid_word_index` |
| pointer emitter | new — §4, port of a tested JS implementation |
| the alignment core (`_build_html_rows`, `_flex_row`, `_row_align`, `_patience_align`) | **unchanged** |

Only the *target* half is medium-specific. 113 of the file's 1,361 lines mention
PDF, and they cluster in `_build_pdf_text_stream`, `_build_mcid_word_index`,
`_phrase_locate`, `_bbox_source`, `_content_sources`, the image-phash helpers,
and the locator emission in `_rewrite`.

Two things are easier than the PDF case: there is no glyph geometry to
reconcile, and the image-phash machinery has no analogue — an HTML5 chart is an
`<img>` that can be pointed at directly.

## 3. Parsing: lexbor, and why it is not optional

`_build_html_model` currently does `etree.parse(htmlPath)`. That cannot be used
for an HTML5 target, for two independent reasons.

**It fails outright.** Microsoft's HTML5 report has 136 unclosed void elements;
`lxml.etree` dies on the doctype:
`StartTag: invalid element name, line 1, column 2`.

**Even where it parses, the tree is wrong.** A pointer's child sequence counts
element children of a *tree*, and HTML5 tree construction differs from libxml2's:

| | lexbor (`selectolax`) | `lxml.html` (libxml2) |
|---|---|---|
| `<tbody>` synthesized where markup omits it | yes | no |
| stray content inside a table | foster-parented out | left inside |
| implied `<head>` | present | absent |

Whether that difference bites is a property of the document:

| document | tables / `tbody` in source | lxml agrees with lexbor |
|---|---|---|
| MSFT HTML5 | 66 / 0 | **18.4%** |
| L'Oréal HTML5 | 3 / 3 | 100% |

There is no way to know which case a document is without checking, so use the
conformant parser always. **Do not fall back to `lxml.html` when `selectolax` is
unavailable** — a fallback returns a real but wrong element, and a plausible
value from the wrong place is worse than no answer. Fail with a clear message.

### 3.1 One traversal, not two

You do **not** need a parallel model builder. The divergences are insertions and
relocations; once lexbor has materialised them, nothing is left to disagree
about. So `_build_html_model` takes one extra branch and everything downstream is
untouched -- no regression risk to the row logic.

> **Corrected 2026-08-21, after implementation.** This section originally
> prescribed parsing with lexbor, *serialising*, and re-parsing with lxml, on the
> evidence that it reproduced the lexbor tree exactly on the Microsoft document
> (8383/8383 elements). That measurement was right about that document and wrong
> as general guidance. Across the 1,600-case html5lib-tests corpus the round-trip
> is structurally faithful in only **1457/1600 (91.06%)**, against **1595/1600
> (99.69%)** for a direct node walk. Both failure modes are silent -- the
> re-parsed tree is well-formed, merely different:
>
> - **Quirks mode.** A legacy or absent doctype is normalised to `<!DOCTYPE html>`
>   on serialisation, so a tree built under quirks rules is re-parsed under
>   standards rules. `<p><table>` nests differently between the two.
> - **Adoption agency.** Misnested formatting elements are not idempotent under
>   the round-trip: `<b>1<i>2<p>3</b>4` yields `p` one level shallower.
>
> Note also that "8383/8383 elements" is element-*count* parity, which is weaker
> than structural: on the corpus, count parity reads 92.69% where structural
> parity reads 91.06%. Assert tag + depth + document order, not counts.

What is implemented instead, in `_parse_source_tree` / `_lexborToLxml`:

```python
if mediaType == "text/html":
    raw  = normalizeNoscript(open(path, "rb").read())    # see 3.3
    root = _lexborToLxml(LexborHTMLParser(raw).root, etree)
else:
    root = etree.parse(path).getroot()                   # XML infoset
```

The direct walk copies tag, attributes and text into lxml elements. It cannot
represent a name that is legal in HTML5 but illegal in XML (`o:p`, `v:shape`,
`ix:header`), and falls back to serialise-and-reparse for those, with a warning
naming which parse was used. Composite: **1600/1600** on the corpus.

**Do not fall back to `lxml.html` when `selectolax` is unavailable** -- a fallback
returns a real but wrong element, and a plausible value from the wrong place is
worse than no answer. Fail with a clear message.

### 3.2 A trap that cost the tagger session an hour

`selectolax`'s `iter(include_text=False)` still yields `-comment` pseudo-nodes.
XPointer `element()` counts **element** children only. One comment near the top
of `<body>` shifts every index beneath it, and the resulting measurements look
like a catastrophic parser disagreement when nothing is wrong. Filter them:

```python
[c for c in node.iter(include_text=False) if not c.tag.startswith('-')]
```

### 3.3 `<noscript>` must be blanked pre-parse

lexbor's scripting flag is off and `selectolax` exposes no way to set it. A
browser parses `<noscript>` content as RAWTEXT; lexbor parses it as elements,
which escape into `<body>` and shift every sibling index after them. Both
demonstration documents are affected -- `msft-ar25-html5.html` leaks a Webtrends
tracking pixel (`div`, `img`) and `loreal-ar25-html5.html` a Google Tag Manager
`iframe`, both near the top of `<body>`, the worst position.

Use `Html5Normalize.normalizeNoscript`. Do **not** write the obvious regex: with
scripting on, noscript content is RAWTEXT, so a `<noscript>` literal inside a
comment or a `<script>` makes a lazy `.*?` span to a later real close tag and
delete every element between. Verified to destroy the entire body of a test
document.

## 4. The pointer to emit

`xbrlx:htmlElementPointer` — an XPointer `element()` scheme child sequence,
written **without** the `element(...)` wrapper.

| form | meaning |
|---|---|
| `currentAssets` | the element whose `id` is `currentAssets` |
| `/1/14` | the 14th element child of the root element |
| `financial-review/2/1` | from the element with that id, 2nd child, then its 1st |

Grammar: `NCName | childSequence | (NCName childSequence)` where
`childSequence ::= ("/" [1-9][0-9]*)+`. Integers are **1-based** and count
element children only.

**Generation rules**, in order of preference:

1. the element's own `id`, if usable;
2. a sequence from the nearest usable ancestor `id` — the **hybrid** form;
3. a full sequence from the document element.

Prefer the hybrid: it is immune to structural change outside its anchor, which
is what a bare sequence handles worst. On the L'Oréal filing, 29% of elements
carry a usable id and a further 29% find one on an ancestor — **58% anchor to an
id** rather than counting from the root.

An `id` is *usable* only if it addresses exactly one element and is an NCName.
Duplicate ids are invalid but occur in filings, and `getElementById` silently
returns the first — which would point a fact at the wrong place with no error.
Skip the anchor and continue upward in that case.

**Verify every pointer as it is generated**: build it, resolve it back, and check
it lands on the element it came from. Every way a pointer goes wrong is silent —
it resolves to a real but different element. The reference implementation does
this and round-trips all 90,908 elements of the L'Oréal filing with zero
failures, at 11.9 µs per element.

### 4.1 It is a port, and it must agree exactly

The reference is JavaScript:
`ixbrl-viewer/iXBRLViewerPlugin/viewer/src/js/xbrlModel/tagging/elementPointer.js`
(`elementPointer`, `resolvePointer`, `verifiedPointer`; 17 unit tests plus the
full-filing round-trip).

The browser tagger generates pointers with it, and the aligner will generate
pointers for the same documents. **If the two disagree, they will silently
produce different addresses for the same element.** Worth a shared corpus —
same documents, same expected pointers, asserted from both languages — rather
than two implementations that are merely believed to match.

## 5. Locator type: record the parse mode

Two types are declared in `resources/xbrlx.json`, split by `sourceMediaType`:

| locator type | `sourceMediaType` | counted against |
|---|---|---|
| `xbrlx:xhtmlPointerLocatorType` | `application/xhtml+xml` | XML infoset |
| `xbrlx:htmlPointerLocatorType` | `text/html` | HTML5 tree |

This is not decoration. On Microsoft's *filed* 10-K — well-formed XML with 85
tables and **zero** `tbody` — the two trees are 67,801 and 67,886 elements, and
**only 4,612 pointers survive a parse-mode swap: 6.8%**. Emit the type matching
the tree you actually counted.

Note the wrinkle: a downloaded EDGAR file carries no Content-Type at all, and SEC
serves inline filings as `text/html` through its own viewer. So for these
documents the XHTML/HTML5 distinction is a property of how the file reaches the
parser, not of how it was authored. Detecting XHTML from content — XML
declaration, XHTML namespace, well-formedness — is the normal path, not a
fallback.

## 6. Multi-fragment values

A fact value assembled from several fragments is **one** `valueSource` whose
locator property holds an ordered array — not one source per fragment.
`xbrl:htmlElementId` and `xbrl:pdfMcid` are declared `xbrlr:stringCollection` in
`core.json`, and this is what `saveOIMFacts` and the existing models already do:

```json
"valueSources": [{"properties": [
    {"property": "xbrl:htmlElementId", "value": ["F_...cd49", "F_...cd49_1"]}]}]
```

L'Oréal's PDF model likewise carries `"xbrl:pdfMcid": [2,3,...,12]` — eleven runs
in a single source. Split into separate sources only where a **scalar** property
differs (`xbrl:pdfPage` is `xs:integer`, so a value spanning a page break is
genuinely two contiguous fragments).

Fragments concatenate with **nothing between them**, and are **not** stripped.
This follows Inline XBRL 1.1 continuations, which `factValueSourceObject`
mirrors: Arelle joins a continuation chain with `"".join` (`XmlUtil.innerText`)
over unstripped text (`ModelInstanceObject.rawValue`, `strip=False`), and
collapses whitespace only later and only where a transform format is present.
Inventing a separator breaks adjacent runs that differ only in styling — `Rev` +
`enue` must not become `Rev enue`.

## 7. Two open anomalies from the Microsoft PDF run

Both are in your territory and may inform the HTML5 design:

```
total facts ......... 1800
located in PDF ...... 1525  (84%)
  by method:  row-granular=1034  token=491  phrase=0  image=0
  by locator: pdfMcid=364  pdfBBox=1161
unlocated ........... 275
```

- **`phrase=0`.** The phrase-locate stage placed nothing, though 275 facts
  reached it unmapped, where on L'Oréal it recovered the sub-MCID cases.
- **`pdfBBox` outnumbers `pdfMcid` 1161 to 364** on a properly Acrobat-tagged PDF
  whose MCIDs extract cleanly. An MCID is the stabler address, so the ratio is
  worth understanding.

**Provenance of these two, stated plainly.** They are read off the tool's own
summary line by the tagger session, which ran `alignFactsToSurface.py` once against
this corpus and did not open its internals. An earlier draft of this note said
"the row-granular path appears to prefer a rectangle even where a marked-content
id was available" — that was an inference from the counts, not something observed
in the code, and it is withdrawn here so it is not mistaken for a diagnosis. The
counts are reliable; any mechanism behind them is not yet established.

Nothing else about the row-granular strategy is known to this session, so there
is no lost-to-compaction context to recover on that point — there was none to
begin with.

84% here against 100% on L'Oréal and 98% on the SEC N-CSRs.

## 8. Corpus

`/Users/hermf/temp/pdf/Microsoft/` — see `FINDINGS.md` there for full
characterisation.

| file | |
|---|---|
| `msft-20250630-ixbrl.htm` | SEC 10-K, inline XBRL 1.1, well-formed XML, 1,889 `ix:` elements, 48 continuations |
| `msft-ar25-html5.html` | public annual report, HTML5, no XBRL, 42 ids / 8,383 elements |
| `msft-fy25-10k.pdf` | 158 pages, Acrobat-tagged, clean MCIDs |
| `msft-facts.json` | factset from `saveOIMFacts`, 1,708 facts |
| `msft-facts-pdf.json` | after `alignFactsToSurface`, 1,525 located |
| `0000950170-25-100235-xbrl.zip` | the filing DTS |

`/Users/hermf/temp/pdf/loreal/loreal-ar25-html5.html` is a second HTML5 report
from a different publisher — useful so the evidence does not rest on one site's
markup habits. Its numbers overlap the tagged L'Oréal filing in 7 values exactly;
the headline figures match only after scale **and rounding** (`€44.05 Bn` against
`44 052,0` millions), which is a different matching problem — see FINDINGS.md.

Factset generation, for reference:

```bash
arelleCmdLine --plugins saveOIMFacts --internetConnectivity online \
    --file 0000950170-25-100235-xbrl.zip --SaveOIMFactspace msft-facts.json
```

## 9. Suggested order

**Status 2026-08-21: steps 1-3 are done.** What they found:

1. ~~Diagnose `phrase=0` and the `pdfBBox`/`pdfMcid` ratio~~ -- **done, and
   neither is a bug.** `phrase=0`: 264 of the 275 residue facts tokenise below
   `_phrase_locate`'s 3-word minimum (numbers cannot be phrases in any medium),
   and the other 11 are date phrases occurring in *zero* MCIDs -- prior-year
   comparatives the PDF does not render. 1161:364 is the PDF's marked-content
   granularity, not a preference for rectangles. **Re-measured after commit
   40afce203**, which fixed a q/Q graphics-state bug that was corrupting MCID
   text: of 1034 row placements, 719 (69%) have no MCID whose whole text keys to
   the cell value (merged cells such as one MCID reading `'7,404 72'`), 235
   emit pdfMcid, 53 collide, 27 are absent. The pre-fix reading of this split --
   843/81%, and later 517 coarse against 296 decoder-gap -- was taken through
   corrupted text and **understated** coarse granularity, because the two causes
   overlapped almost totally. So 772 of 1034 (75%) is what text-offset addressing
   dissolves, and 719 of that is a floor no decoding moves. Consequence for this
   port: **do not carry the bbox/mcid hybrid across** -- it works around
   granularity we do not control, and container + offset dissolves it.
2. ~~Add the lexbor parse branch~~ -- **done**, `_parse_source_tree` /
   `_lexborToLxml`, see the correction in 3.1. Media type is a required argument.
3. ~~Port the pointer generator, with a shared corpus~~ -- **done**,
   `../HtmlElementPointer.py`. Round-trips 8381/8381, 1434/1434 and 67801/67801
   elements across the three documents, 5.9-14.1 us/element. Anchoring is better
   than 4. predicted: 98% / 84% / 64% resolve to an id rather than counting from
   the root.

   **Corpus landed 2026-08-21**, and it caught two live disagreements before it
   was even committed -- so 4.1's "rather than two implementations that are
   merely believed to match" was not a hypothetical worry.

   * `tests/resources/html-element-pointer/` in this repo is canonical and holds
     the generator; `iXBRLViewerPlugin/viewer/src/js/xbrlModel/tagging/corpus/`
     is a byte-identical 24 KB mirror. Mirrored, not fetched: `node-tests.yml`
     checks out the viewer alone, so a fixture reachable only through a sibling
     checkout would never run in its CI. Both suites pin the expectations'
     SHA-256 in a `CORPUS_SHA256` literal, so regenerating one side without the
     other fails rather than drifting.
   * Three small fixtures, not the demonstration documents: `tiny.xhtml`,
     `tiny-html5.html` (new -- no XBRL, no ids on figures, omitted `<tbody>`,
     two numbers in one `<p>`), and `adversarial.html`. The heavy documents stay
     a local confidence run.
   * The two disagreements it found, both silent, both now fixed. **An accented
     id**: Python's `\w` is Unicode-aware and JavaScript's is not, so the same
     pattern text made `id="résultat-net"` a usable anchor here and not there
     (`9e59194ec`). **The first of a duplicated id**: `isUsableAnchor`'s
     `catch { getElementById(id) === el }` answers *true* for it, inverting the
     guard -- and jsdom implements no `CSS`, so `CSS.escape` threw and the
     viewer's entire jest suite ran that branch while browsers ran the other
     (`c9090548` in the viewer). Its existing test asserted on the *second*
     duplicate, which both branches reject, so 16/16 passed throughout.
   * Note for whoever extends it: `<noscript>` is deliberately absent from the
     fixtures. Normalization is `Html5Normalize`'s job and is tested separately;
     jsdom's scripting flag differs from a browser's, so a noscript fixture
     would compare two things at once. Keep the corpus on pointer generation.

4. ~~Build the target token stream and word index; reuse the alignment core~~ --
   **done**, `_build_html5_target` / `_html5TextRuns` / `_patience_align`.
5. ~~Emit with the locator type matching the parse mode and the collection
   encoding for multi-fragment values~~ -- **done**, `alignToHtml5`, emitting the
   `xbrlx:htmlElementPointer` / `htmlTextOffset` / `htmlTextQuote` triple as
   parallel collections, with `html5Source` / `html5Map`.

   Landed in `8f751c34e` ("HTML5 fact alignment end to end, and text-offset
   locators for both surfaces"), with `b2761ef68` making the text offsets
   integers. **The status line above went stale for nine days**, which is worth a
   note in itself: a handover that says work is outstanding after it has been
   done costs the next reader more than one that says nothing.

## 10. What is actually open

**10.1 Not reachable from the plugin command line.** `PdfToolsCli` wires
`--inline-to-pdf` and `--align-to-pdf` with their options; there is no
`--align-to-html5`. `alignToHtml5` runs only through the tool's own `__main__`
(`python3 tools/alignFactsToSurface.py …`). Given the sibling operations are both
wired, this looks like an oversight rather than a decision, and it is a small
one to close.

**10.2 It emits a rewritten factset, and by a decision taken since, it should
emit derived content.** `alignToHtml5` writes a new facts document with the
locators pointing at the second surface. That predates the derived-content work
(`HANDOVER-model-workflow.md` §8.5, and the OIM Taxonomy Derived Content
specification), which settled that **who is running the tool decides what the
artifact claims**:

* A preparer tagging a report they are authoring produces their own content, and
  it belongs in the model.
* A **later party** — anyone aligning a filing's facts onto a rendering somebody
  else produced — is recording a finding *about* somebody else's report. That is
  derived content: `derivedContent.factValues` with a `basis` of `bound`,
  carrying the pointer / offset / quote triple, beside a model left as filed.

Aligning is the clearer case of the two, because nobody would claim a filer
asserted where their numbers appear in a magazine-layout annual report they did
not publish. It is also the same operation the tagging journal performs by hand,
and the two currently produce different shapes for the same kind of finding —
`ApplyTaggingJournal` records a binding, the aligner rewrites the model.

Note this is a change of *output*, not of alignment: everything in §1--§9 above
stands, and steps 1--5 do not need revisiting. What changes is where the located
pointers are written.

**10.3 Both outputs are wanted, by different parties — the same axis as §8.5.**
Settled with the spec author, and it is not a choice between them:

* **A preparer aligning onto their own surfaces.** They file formally as XHTML
  (or, in time, PDF or HTML5 where a regulator accepts it), and then map the same
  tagging onto the glossy interactive HTML5 report on their own website. Both
  surfaces are theirs, and saying where their data appears on their own site is
  their own assertion. Output: the **model**.
* **Anyone else.** An authority taking XHTML filings and providing a derived PDF
  for dissemination convenience; a data aggregator — Bloomberg and the like —
  applying tagging to reports they format for their own audiences. None of that
  is the filer's content. Output: **derived content**, `basis: bound`.

So the aligner takes the same option the journal applier already has, with the
same semantics and the same default:

    --taggingJournalInto model | derivedContent      (ApplyTaggingJournal)
    --align...Into            model | derivedContent      (the aligner)

which is what closes the divergence in 10.2 rather than merely moving it.

**For the preparer case, the product is probably not a second factset.** The
model already carries several surfaces in one document, and this is exactly what
it is for: `reportSource` on a fact value is documented as needed "if there is
more than one source file used to represent fact values", `documentInfo.
sourceMappings` is a set whose own example maps two fact sources to two
documents, and `FactValueResolver` already selects the mapping by `reportSource`.
So a preparer's aligned output can be **one model whose facts carry value sources
for the filing and for the website**, each tagged with its `reportSource`, and a
consumer picks the surface — rather than two factsets that must be kept in step.

That is the design question for the session: confirm the multi-surface model
works end to end (the loader sets `reportSource` to None today — see the
TODO(multi-doc) in `LoadInlineFacts`), and only fall back to parallel factsets if
it does not.

**Decision taken for step 5:** emit *corroborated* pointers --
`xbrlx:htmlTextQuote` and `xbrlx:htmlTextOffset` alongside the required
`xbrlx:htmlElementPointer` -- rather than a bare positional path. This is a
correctness requirement, not the robustness improvement 6. framed it as: in a
legacy inline document every fact has its own `ix:` element, so element
addressing is exact by construction, but in an HTML5 report the taggable numbers
sit in running prose. **27%** of the numbers in `msft-ar25-html5.html` share an
element with another number (worst `<p>`: 14 of them), and 14% in loreal, so an
element pointer alone cannot say *which* number is the fact.

Consequently the three `xbrlx` properties are now `xbrlr:stringCollection`, not
`xs:string`: 6. requires a multi-fragment value to be one `valueSource` holding
an ordered array, which `xs:string` cannot express. Fragment *i* has
pointer[i], quote[i], offset[i].
