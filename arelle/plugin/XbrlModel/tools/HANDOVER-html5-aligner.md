# Handover: an HTML5 target for the fact aligner

For the session that owns `tools/alignFactsToPdf.py`.

`alignFactsToPdf` maps facts from a tagged inline document onto a *second*
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
about. Parsing with lexbor, serialising, and re-parsing with lxml reproduces the
lexbor tree exactly — verified on the Microsoft document, 8383/8383 elements:

```python
if mediaType == "text/html":
    root = lxml.html.fromstring(LexborHTMLParser(src).html)   # HTML5 tree
else:
    root = etree.parse(path).getroot()                        # XML infoset
```

So `_build_html_model` takes one extra branch and everything downstream is
untouched — no regression risk to the row logic. Costs one serialise-and-reparse
pass.

### 3.2 A trap that cost the tagger session an hour

`selectolax`'s `iter(include_text=False)` still yields `-comment` pseudo-nodes.
XPointer `element()` counts **element** children only. One comment near the top
of `<body>` shifts every index beneath it, and the resulting measurements look
like a catastrophic parser disagreement when nothing is wrong. Filter them:

```python
[c for c in node.iter(include_text=False) if not c.tag.startswith('-')]
```

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
  whose MCIDs extract cleanly. The row-granular path appears to prefer a
  rectangle even where a marked-content id was available; an MCID is the stabler
  address.

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
| `msft-facts-pdf.json` | after `alignFactsToPdf`, 1,525 located |
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

1. Diagnose `phrase=0` and the `pdfBBox`/`pdfMcid` ratio — both are PDF-side and
   may change what the HTML5 target should do.
2. Add the lexbor parse branch to `_build_html_model` (§3.1).
3. Port the pointer generator, with a shared corpus asserting agreement with the
   JS reference (§4.1).
4. Build the target token stream and word index; reuse the alignment core.
5. Emit with the locator type matching the parse mode (§5) and the collection
   encoding for multi-fragment values (§6).
