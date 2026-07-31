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
| `xbrl:pdfContentLocatorType` | `pdfPage` (int) + `pdfMcid` (int array) | marked-content glyphs | visible facts whose value fills their MCID(s) |
| `xbrl:pdfImageLocatorType` | `pdfPage` + `pdfBBox` (`"x0 y0 x1 y1"`) + optional `pdfImageHash` (`md5:…`) | a rectangular region | a chart **image**, or a sub-MCID text value's glyph box (see below) |
| `xbrl:pdfFormFieldLocatorType` | `pdfFormField` | an AcroForm field value | facts sourced from PDF form fields |
| `xbrl:htmlElementLocatorType` | `htmlElementId` | HTML element text | fallback for facts not located in the PDF |

`pdfBBox` is in PDF user-space points, origin lower-left. For a **chart image**,
one region is typically referenced by many facts (see §3), so highlighting is
region-level, not per-value.

**Sub-MCID text values (hybrid content/bbox locator).** Accessibility tagging is
often *row-grained*: a whole table row — `TOTAL GROUPE 41 182,5 43 486,8 44 052,0
…` — is a single marked-content id, so a `pdfMcid` locator for one figure would
highlight the entire row. When a fact's value is only a **portion** of its MCID,
`alignFactsToPdf` instead emits a per-value `pdfBBox` — the glyph rectangle of
just that value, computed with pypdfium2 and disambiguated by the MCID row text —
carried on the image source (which viewers already render). A fact that *is* its
whole MCID(s) keeps the structural, reflow-robust `pdfMcid`. So for text a
`pdfBBox` is per-value; for a shared chart image it stays region-level. The bbox
is only emitted when its value is confidently placed (found within its row, or
unique on the page); otherwise the fact safely keeps its correct-row `pdfMcid`.

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
  fields; whole-MCID text goes to the content source, sub-MCID text values and
  chart images to the image source (see §2), and facts not found in the PDF keep
  a valid html-fallback locator.

Both tools can also be run standalone (`python3 tools/<tool>.py --help`).

---

## 5. GUI operation

In the Arelle desktop application (started with the XbrlModel plugin enabled),
the plugin adds model viewing, model saving, and the PDF tools.

### Viewing a model

Open a compiled XbrlModel JSON — or a report loaded as an entry point — via
**File ▸ Open File…**. The plugin replaces the ordinary taxonomy views with
tabbed views of the model's objects: **Concepts, Groups, Networks, Cubes, Domain
Networks**, and — when the model carries facts — **Taxonomy Facts**, plus (as
additional views) **Cube Facts**, **Import Taxonomies**, Group Tree, Headings,
Cube Types, Data Types, Dimensions, Entities, Labels and Label Types, Property
Types, References and Reference Types, Relationship Types, Transforms and Units.
(Hook: `CntlrWinMain.Xbrl.Views`, `xbrlModelViews`; the views themselves are
`ViewXbrlTaxonomyObject.py`.)

**Validation on load.** A compiled model is validated on load by default, before
the views are built, so the concept / fact / cube views reflect resolved fact
dimensions and values, cube-fact assignments and any validation errors — and, for
streamed fact sources, each streamed row is validated before the next replaces
it. Deferring validation (for a report still being formed, or one problematic to
validate) is available via **Tools ▸ "Validate XBRL model on load"** (a checked-
by-default toggle stored in the config); the toolbar **Validate** button then
validates on request.

**Groups is the reporting structure.** Rather than a flat list, the Groups pane
nests groups under the model's `groupTree` object in relationship order, each
group followed by its group contents (networks, cubes, table templates), which in
turn expand into cube dimensions, domain networks and their members. Groups the
tree does not reach appear under an **(ungrouped)** node, so nothing is hidden; a
model with no `groupTree` falls back to a flat list of groups. For a legacy DTS
loaded through `LoadLegacyTaxonomy`, the inferred tree gives the familiar SEC
Cover / Statements / Notes / Policies / Tables / Details sections.

**Cube Facts** shows the group tree of cubes, each cube followed by the facts
assigned to it. The assignment is *derived* — candidate facts are those whose
concept is a cube line item, then filtered by the full dimensional match
(`matchFactToCube`), the same normative rule validation uses — so it is available
without a prior validation pass and is dimensionally correct (a fact carrying an
axis the cube lacks is excluded, not placed by concept alone). Facts appear in
presentation order; cubes reached by no group go under **(ungrouped)**. Its
right-click **Cube facts options** submenu toggles *Show empty groups*, *Show
empty cubes*, *Show name column* and *Show kind column* (empties and the kind
column are hidden by default). When the proposed `cubeContents` objects are
adopted the pane would read them in preference to deriving.

**Import Taxonomies** is a tree: each imported module nested under the module that
imports it, so the hierarchy shows which taxonomy imports which. Roots are the
modules imported by no other module (typically the entry-point taxonomy); cycles
among the built-in modules are marked **(loop)** and not re-descended.

**Columns.** The tree column shows each object's label in the pane's current
label role and language. The structural panes (Groups, Group Tree, Cubes,
Networks, Domain Networks) put objects of different types on successive rows, so
their columns are type-neutral — **object** (the row's object type), **name**,
**kind** (the property that discriminates the type: a cube's cubeType, a cube
dimension's dimension, a network's relationship type) — while the other panes
keep their object class's own properties as columns. Every pane ends in a
**detail** column carrying whatever has no column of its own, as `name=value`
pairs. Cells are always filled by column name, so a value only ever appears under
a heading that names it. Long role URIs are shortened from the left
(`…/role/CoverPage`) so the identifying trailing segment stays visible; hover for
the full text.

Column widths are startup defaults — like every other Arelle view, the GUI
persists window geometry and the tab splitters but not column widths. The last
(**detail**) column absorbs the pane's spare width, so resizing a column resizes
only that column and the label column keeps its width.

**Context menu** (right-click / control-click): Expand and Collapse, **Find…**
(repeat to step through matches, wrapping at the end), Copy to clipboard (cell,
row or whole table as tab-separated text), **Copy JSON** (the selected object
serialized as its compiled JSON), Language, Label role (including *Name* to show
QNames), Name Style (prefixed QNames or local names), and **View ▸ Additional
view**, which lists every pane — including those opened on load — so a pane that
has been closed can be reopened. Hovering a **detail** cell shows its properties
one per line. An opened tree keeps its expansion when the label role, language,
name style or sort changes.

**Selecting a row** synchronizes the other panes to the same object and fills two
panes in the upper-left tab window: **Properties** (from the object's
`propertyView`) and **JSON** (the object's compiled JSON, via
`SaveModel.saveableObjects`). Sync is by object identity, but the Facts and Cube
Facts panes also index each fact under its dimension members, so selecting a
concept or unit reveals a fact that uses it, and selecting a fact reveals its
concept in the Concepts pane and its unit in the Units pane. In the Properties
pane a fact's dimensions are flat rows (no expanding per fact), while its
`factValues` expand to show `value`, `decimals`, any transformation, and the
`valueSources` locating the value in the source document — for an inline or PDF
report, the html element id the fact was tagged from.

**Find** — the infrastructure Find dialog (toolbar, or Tools ▸ Find) searches the
compiled model too: its concept and fact field checkboxes match `XbrlConcept` /
`XbrlFact` objects, and stepping through results highlights them across the panes.
(Hook: `DialogFind.Objects`, handler `findObjects`.) A non-XbrlModel DTS falls
back to the dialog's ordinary search.

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
- **Aligner match pipeline.** Each fact is placed by the first strategy that
  succeeds, most-structural first (the run prints a `[summary]` block: located %,
  by method, by locator, and how many stay on the html fallback):
  1. **Row-granular signature match (primary).** The HTML DOM's table structure
     is *trusted*: a fact's `<tr>` yields a row **signature** — label + ordered
     value cells. A Key-Facts-style leaf `<li>` that carries a label next to a
     value fact (`Total Number of Portfolio Holdings 75`) is treated as a row too,
     so those flex/list items align like table rows. The PDF side is rebuilt from **glyph geometry, not its structure
     tags** (which mis-tag merged cells — horizontally or vertically): chars are
     clustered into rows by y-band and split into cells at column-scale x-gaps
     (not the smaller thousands-space, which would fragment `8 687,5`). HTML rows
     are matched to PDF rows by a **monotone** (top-to-bottom in both documents)
     weighted DP on the signature — far more distinctive than a bare value, so a
     figure repeated across statements / 2- vs 3-period presentations lands in its
     correct row. A **contiguity bonus** rewards consecutive rows on the same/
     adjacent page, so a table duplicated in the report (e.g. a condensed income
     statement in the commentary *and* the official one in the financials) maps as
     one block to its real occurrence instead of splitting across the copies.
     Values match on **magnitude** (sign/paren/space-stripped), so an
     `ix:nonFraction sign="-"` that omits the sign vs a PDF `-` / `- ` / `(…)`
     convention does not break the row (placement still uses the PDF glyph box).
     Two further layout defences matter for multi-fund books (SEC N-CSRs): a band
     holding two **side-by-side tables** is split into per-column rows at a wide
     `numeric → text` boundary (a value followed across a gutter by a new label),
     so `(0.14)% | Industrial 18.98%` becomes two rows rather than one merged row
     that only one html row could claim — while a genuine multi-value row
     (`Résultat net 6133,7 6416,5 6190,5`, all-numeric after the label) is never
     split. And when the html has many repeated **section headers** (`<h1>` fund
     reports — hundreds of near-identical tiny tables), each header is found in the
     PDF (by its ticker/name) and a fact gets a **soft score bonus** for matching
     inside its own fund's PDF page range — enough to defeat the cross-fund
     repetition, but never a hard filter, so an imperfect header mapping degrades
     to global matching instead of dropping the fact.
     A cell that is exactly one whole MCID keeps the reflow-robust `pdfMcid`; a
     cell inside a coarse/merged MCID gets its own glyph `pdfBBox`.
  2. **Token patience alignment (fallback)** for facts not in a table (narrative)
     or in rows that did not match: HTML and PDF are reduced to document-order word
     streams and aligned with a **recursive patience alignment** (anchor on tokens
     locally unique within each gap, recurse, `difflib` only on tiny base gaps; a
     global `difflib` on ~360 k-token streams never finishes). Clip-hidden subtrees
     are excluded (not in the PDF).
  3. **Phrase-locate fallback** for anything still unmapped (prose text blocks,
     addresses): the fact's distinctive text is matched as a **phrase** against the
     MCID cache (a word inverted index + longest common contiguous run, expected
     page breaking ties). Patience alignment anchors on *unique* tokens and skips
     anchor-less prose even when it is present as one clean MCID; a phrase (a run
     of common words) is distinctive where its words are not.
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
| [`tools/alignFactsToPdf.py`](tools/alignFactsToPdf.py) | match facts to an existing PDF (row-granular signature match → token patience-align → phrase-locate → image pairing) |
| [`PdfTextExtractor.py`](PdfTextExtractor.py) | tagged-PDF text by mcid / struct-id / form field (page-scoped) |
| [`PdfToolsCli.py`](PdfToolsCli.py) | command-line options + dispatch (wired from `__init__.py`) |
| [`FactValueResolver.py`](FactValueResolver.py) | resolves html / pdf locators to source text during validation |
| [`loadFromPDF.py`](../loadFromPDF.py) | read a tagged PDF + template into facts (the reverse, standalone PoC) |

Spec: locator property types and fact locator types are defined in
`specifications/oim-taxonomy/oim-taxonomy.md`.
