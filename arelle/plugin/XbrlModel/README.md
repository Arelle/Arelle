<!-- See COPYRIGHT.md for copyright information. -->

# XBRL Model plugin

Loads OIM-Taxonomy objects and facts from JSON (per the Open Information Model
Taxonomy specification), validates the compiled model, and serializes it back to
JSON / CBOR / Excel. See the module docstring in [`__init__.py`](__init__.py) for
loading and the compiled-model save modes (`full` / `prune` / `report`,
[`SaveModel.py`](SaveModel.py)).

This README documents the **PDF ⟷ fact-locator workflow** — the part that spans
several modules and whose design rationale is otherwise spread across the code
and the spec.

---

## 1. What the PDF workflow does

An inline-XBRL report can be paired with a PDF so that each fact knows **where it
appears in the PDF**. That location is recorded on the fact's `valueSources` (or
`valueAnchors`) using the PDF locator property types defined in
`oim-taxonomy.md` (§ *Locator-specific property types* / *Fact locator types*).
A viewer can then highlight the PDF region for a selected fact, and a resolver
can extract the source text for validation.

There are **two directions**, each a standalone tool under [`tools/`](tools) and
wired to the command line (see §4):

| Direction | Tool | Use when |
|---|---|---|
| **Generate** a tagged PDF from the HTML | [`tools/inlineXbrlToPdf.py`](tools/inlineXbrlToPdf.py) | No good PDF exists; you want a self-contained traceable PDF |
| **Match** facts onto an existing tagged PDF | [`tools/alignFactsToPdf.py`](tools/alignFactsToPdf.py) | A filer/Acrobat PDF exists and looks better than anything rendered |

Both consume the *html-locator* facts file produced by `saveOIMFacts`
(`--plugins saveOIMFacts --SaveOIMFactspace facts.json`), whose fact values carry
`xbrl:htmlElementId` locators, and rewrite those to PDF locators.

---

## 2. The four locator types

| Locator type | Properties | Resolves to | Produced for |
|---|---|---|---|
| `xbrl:pdfContentLocatorType` | `pdfPage` (int) + `pdfMcid` (int array) | marked-content glyphs | visible facts (aligned text) |
| `xbrl:pdfImageLocatorType` | `pdfPage` + `pdfBBox` (`"x0 y0 x1 y1"`) + optional `pdfImageHash` (`md5:…`) | a rectangular image region | facts whose visual is a chart **image** |
| `xbrl:pdfFormFieldLocatorType` | `pdfFormField` | an AcroForm field value | facts sourced from PDF form fields |
| `xbrl:htmlElementLocatorType` | `htmlElementId` | HTML element text | fallback for facts not located in the PDF |

`pdfBBox` is in PDF user-space points, origin lower-left. **One chart image is
typically referenced by many facts** (see §3), so highlighting from a
`pdfImageLocator` is region-level, not per-value.

A small end-to-end fixture — source HTML, a chart image, a 1-page tagged PDF, and
an aligned factset that resolves all four locator types — is the fastest way to
develop a consumer (viewer / resolver). One can be produced with `alignFactsToPdf`
plus a hand-added AcroForm field for the form-field case.

---

## 3. Why fixed-layout SEC N-CSRs are special

SEC "Tailored Shareholder Report" N-CSRs encode most of their facts
(≈ 85 %: the *growth of a hypothetical $10,000 investment* series,
`oef:AcctVal`) in a **`clip: rect(0,0,0,0)` visually-hidden data table** sitting
beside a **chart `<img>`**. The numbers are present for machine-readability but
are **invisible on screen by design**; the visual is the chart image.

Consequences the tools are built around:
- No PDF converter (Acrobat, Chrome, WeasyPrint, Prince…) can render those hidden
  numbers as visible text — a faithful PDF shows the *chart*, not the data.
- The **generator** only recovers them by *reflowing* (un-hiding) the layout,
  which sacrifices the preparer's appearance.
- The **aligner** cannot match them as text, so it pairs the hidden data table to
  its sibling chart image and anchors those facts to the **image region**
  (`pdfImageLocatorType`).

Reflowable reports (e.g. an ESEF annual report) have none of this and locate
100 % via text.

---

## 4. Operating the tools (command line)

Prerequisite (both directions):

```bash
arelleCmdLine --plugins saveOIMFacts --file report.xhtml \
    --SaveOIMFactspace report-html-facts.json
```

### Generate a traceable tagged PDF

```bash
arelleCmdLine --plugins XbrlModel --inline-to-pdf \
    --ix-html report.xhtml --ix-facts report-html-facts.json --ix-pdf report.pdf
```
- `--ix-engine chrome` (default; scales to 100s of MB) or `weasyprint`
  (deterministic, small filings only).
- `--ix-no-reflow` keeps the fixed (absolute) layout — faithful appearance but
  clipped facts become unlocatable; omit it (default reflow) for full coverage.
- Emits `pdfContentLocatorType` locators and embeds the facts JSON in the PDF.

### Match facts onto an existing tagged PDF

```bash
arelleCmdLine --plugins XbrlModel --align-to-pdf \
    --al-html report.xhtml --al-facts report-html-facts.json \
    --al-pdf filer-or-acrobat.pdf --al-out-facts report-pdf-facts.json
```
- The PDF must be **accessibility-tagged** (marked content). Acrobat *autotag*
  tags text but usually leaves chart images untagged — hence the image locator.
- Output has three sources (html / content / image) plus, when present, form
  fields; facts not found in the PDF keep a valid html-fallback locator.

Both tools can also be run standalone (`python3 tools/<tool>.py --help`).

---

## 5. GUI operation

In the Arelle desktop application (started with the XbrlModel plugin enabled),
the plugin adds model viewing, model saving, and the PDF tools. The GUI is
functional but intentionally minimal — a proof-of-concept UX.

### Viewing a model

Open a compiled XbrlModel JSON — or a report loaded as an entry point — via
**File ▸ Open File…**. The plugin replaces the ordinary taxonomy views with
tabbed views of the model's objects: **Concepts, Groups, Networks, Cubes, Domain
Networks**, and — when the model carries facts — **Taxonomy Facts**, plus
Headings, Cube Types, Data Types, Dimensions, Entities, Group Tree, Labels and
Label Types, Property Types, References and Reference Types, Relationship Types,
Transforms and Units. A report opened as an entry point is validated on open so
the fact and concept views populate. (Hook: `CntlrWinMain.Xbrl.Views`,
`xbrlModelViews`.)

### Saving a model

**File ▸ Save** (GUI) or **`--saveOIMmodel <file>`** (command line) serializes the
loaded model as a single OIM *compiled* model (documentType `…/2026/compiled`).
Output format (JSON / CBOR / Excel) follows the file extension. The mode is chosen
in a modal on GUI Save, or with the CLI `--oimSaveMode` option / the formula
parameter `oimSaveMode` (default `full`):

- **`full`** — every discovered object and all facts, as loaded.
- **`prune`** — the *interpretation-minimal* closure: only the taxonomy objects a
  consumer needs to *interpret* the reported facts (their concepts, dimensions,
  members, datatypes, labels, units). Networks, cubes and the reporting structure
  are dropped — a self-describing fact carries its own factDimensions.
- **`report`** — the *semantic / consumable* closure: the `prune` closure **plus**
  the presentation networks and cubes that organise the reported facts, and the
  reporting-structure groups + `groupTree` that section them, with facts tailored to
  viewer Form B. **Empty abstract subgroups** — sections that organise no reported
  fact — are dropped like any other unused object, so the section tree a viewer or an
  LLM/MCP consumer navigates carries no empty noise.

This lets a facts-only aligned-facts module that imports its taxonomy (e.g. a legacy
DTS bound via `importMapping`) be loaded and re-emitted as a complete, self-contained
compiled model. See the [`__init__.py`](__init__.py) header and
[`PruneModel.py`](PruneModel.py). (Hooks: `CntlrWinMain.Xbrl.Save`;
`CntlrCmdLine.Xbrl.Loaded` for the command line.)

### PDF fact-locator tools

The **Tools** menu adds two items. Neither requires a model to be loaded — they
prompt for the files and run in a background thread (large filings take minutes;
progress shows in the status bar, completion/errors in the log):

- **Inline XBRL → tagged PDF (generate)…** — choose the inline document and the
  html-locator facts JSON, then an output PDF. Writes the PDF and a sibling
  `<pdf>-pdf-facts.json`.
- **Locate facts in existing tagged PDF…** — choose the inline document, the
  html-locator facts JSON, and an existing tagged PDF, then the output facts
  JSON.

GUI runs use the defaults (chrome engine, reflow on). For a different engine
(`weasyprint`), `--no-reflow`, or scripted/batch use, use the command line (§4).

---

## 6. Design notes (the "why")

- **Engine choice.** WeasyPrint is deterministic (a hookable render loop) but does
  not scale — an 11 h+ non-finish on a 182 MB filing. Chrome renders the same in
  minutes, so it is the default engine. WeasyPrint remains for small deterministic
  cases.
- **XHTML, not HTML5.** Inline XBRL must render in XML mode. A `.xhtml` file
  extension (local) or `Content-Type: application/xhtml+xml` (HTTP) forces
  Chrome's XML parser; HTML5 mode mis-parses `ix:` elements and nested markup.
- **Carrier for the generator.** Chrome does not carry the HTML `id` onto PDF
  structure, and `<a>` link annotations cannot nest (they collapse to the
  outermost, ~13 % on deeply-nested filings). The generator therefore injects
  balanced transparent `⟦N⟧…⟦/N⟧` **text tokens** inside each fact element and
  reconstructs `factId → (page, mcid)` from the marked-content stream — tokens are
  independent text and survive arbitrary nesting.
- **Aligner text match.** The HTML and PDF are reduced to document-order word
  streams and aligned with a **recursive patience alignment** (anchor on tokens
  locally unique within each gap, recurse, `difflib` only on tiny base gaps);
  a global `difflib` on ~360 k-token streams never finishes. Clip-hidden subtrees
  are excluded from the alignment (they are not in the PDF).
- **Aligner image match.** Each HTML `<img>` is matched to a PDF image XObject by
  content hash (exact md5, with a 64-bit **dHash** perceptual fallback for JPEGs
  Acrobat re-encoded), and its placement (page + bbox) recovered from the
  content-stream CTM. When an image is placed on several pages, the placement
  nearest the chart's document position (via the nearest content-located fact's
  page) is chosen. `pdfImageHash` stores the PDF image's **exact** md5; the dHash
  is only an authoring-time pairing aid, so no spec change is needed.
- **Resolver performance.** [`PdfTextExtractor`](PdfTextExtractor.py) resolves a
  single `pdfMcid` by walking only that one page (`_pageMcidText`), ~0.2 s vs a
  ~10 s full-document walk; the full walk is built only when the whole stream is
  needed (the aligner).

---

## 7. Files

| File | Role |
|---|---|
| [`tools/inlineXbrlToPdf.py`](tools/inlineXbrlToPdf.py) | generate a tagged PDF (Chrome/WeasyPrint), token carrier, reflow |
| [`tools/alignFactsToPdf.py`](tools/alignFactsToPdf.py) | match facts to an existing PDF (text patience-align + image pairing) |
| [`PdfTextExtractor.py`](PdfTextExtractor.py) | tagged-PDF text by mcid / struct-id / form field (page-scoped) |
| [`PdfToolsCli.py`](PdfToolsCli.py) | command-line options + dispatch (wired from `__init__.py`) |
| [`FactValueResolver.py`](FactValueResolver.py) | resolves html / pdf locators to source text during validation |
| [`loadFromPDF.py`](../loadFromPDF.py) | read a tagged PDF + template into facts (the reverse, standalone PoC) |

Spec: locator property types and fact locator types are defined in
`specifications/oim-taxonomy/oim-taxonomy.md`.
