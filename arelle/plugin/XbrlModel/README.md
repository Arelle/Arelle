<!-- See COPYRIGHT.md for copyright information. -->

# XBRL Model plugin

Loads OIM-Taxonomy objects and facts from JSON (per the Open Information Model
Taxonomy specification), validates the compiled model, and serializes it back to
JSON / CBOR / Excel. See the module docstring in [`__init__.py`](__init__.py) for
loading and the compiled-model save modes (`full` / `prune` / `report`,
[`SaveModel.py`](SaveModel.py)).

This README documents the two workflows that span several modules and whose
rationale is otherwise spread across the code and the spec: **filing → compiled
model → viewer** (quick start below, GUI in §5) and **putting a filing's facts
onto a second surface** — a PDF, or a published HTML5 report that carries no
XBRL — so the same data can be seen wherever the report is actually read
(§1–§4).

---

## Quick start — a filing to something you can look at

An EDGAR filing (or an ESEF report package, an inline `.htm`, an XBRL 2.1 `.xml`
instance, an xBRL-JSON/CSV report, a legacy `.xsd` entry point, or an OIM
`.json`/`.cbor` model) loads directly into the XBRL Model. One command turns it
into a self-contained compiled model plus a servable viewer:

```bash
arelleCmdLine --plugins "XbrlModel|<path>/iXBRLViewerPlugin|<path>/EDGAR/transform" \
    --internetConnectivity online \
    -f 0000950170-25-100235-xbrl.zip --saveXbrlModelViewer out/
cd out && python3 -m http.server 8000     # then open ixbrlviewer.html
```

Three plugins, each for a distinct reason:

| plugin | why |
|---|---|
| **XbrlModel** | the model, its validation, the views, and the staging |
| **iXBRLViewerPlugin** | only its **built** bundle (`viewer/dist/ixbrlviewer.js`) is used — the viewer's XbrlModel overlay renders a plain document against an OIM model, so no viewer *document* is built |
| **EDGAR/transform** | supplies the `ixt-sec:*` transformation **functions** for a US filing (§"Transformation registries" below). Not needed for ESEF |

In the **GUI** the same thing happens on **File ▸ Open File…**: load, validate,
build the Tk views, then open the browser — see §5.

Measured on Microsoft's FY2025 10-K (8.4 MB inline document, 2 MB extension
schema, `us-gaap`/`dei`/`ecd` fetched and cached):

| | |
|---|---|
| wall clock | ~6 s (first run slower — the base taxonomies download) |
| compiled model | 9.3 MB, one file, **no separate taxonomy needed** |
| | 12,488 concepts · 124 cubes · 145 networks · 129 groups · groupTree |
| | 1,829 facts, 1,827 of them located by `xbrl:htmlElementId` |
| in the viewer | **2,146 bound fact overlays** over the inline document |
| log | 42 messages: **31 findings** — 21 calculation inconsistencies and 10 on `ecd:` compensation members declared as concepts rather than members — and 11 informational |

Drop `--saveXbrlModelViewer out/` for `--saveOIMmodel model.json` to get just the
model (`--oimSaveMode full|prune|report`). Both **validate the model first**,
whether or not `--validate` was given: a legacy report opened as an entry point
materializes its facts at validate time, and the artifact is meant to carry the
validation verdicts.

### Transformation registries

A value re-derived from the document is transformed by the registry the fact
names. The standard registries (`ixt`, `xbrltt`) are built into Arelle; anything
else is contributed by a plugin through `ModelManager.LoadCustomTransforms`,
which is how **EDGAR/transform** supplies SEC's `ixt-sec:*` functions. Without it
a US filing's ballot boxes and spelled-out numbers stay as document text and then
fail their concept's datatype. The matching *declarations* (transform objects and
their input datatypes) ship in
[`resources/sec-transform-types.json`](resources/sec-transform-types.json),
generated from SEC's own registry by
[`tools/genSecTransformTypes.py`](tools/genSecTransformTypes.py).

---

## 1. What the second-surface workflow does

A report is filed once and read in several places: as the filed inline document,
as the polished annual report on the company's website, as a PDF. Only the first
carries XBRL. These tools put the filing's facts onto the *other* renderings, so
the same data can be seen wherever the report is actually read.

Two situations motivate it, and both are ordinary:

- **A published report with no XBRL at all.** Microsoft's and L'Oréal's public
  annual reports are HTML5 sites, professionally laid out and read far more than
  the filing. Aligning the filing's facts onto one makes it navigable as XBRL
  without anyone re-tagging it. `msft-ar25-html5.html` carries 42 `id`
  attributes across 8,383 elements, none of them on a figure, which is why
  element pointers with text offsets exist.
- **A filing too unwieldy to read as filed.** An SEC N-CSR runs to hundreds of
  pages of fixed-layout XHTML that no viewer opens comfortably. Rendering it to
  PDF and aligning the facts onto that gives something a reader can actually use.

**Who is aligning decides what the result claims**, on the same axis as
§"Applying a tagging journal" below:

- **The preparer**, mapping their own tagging onto their own website's report as
  well as onto the formal filing. Both surfaces are theirs, so where their data
  appears on their own site is their own assertion, and it belongs in the model.
- **Anyone else** — an authority deriving a PDF from XHTML filings for
  dissemination, or a data aggregator tagging reports it formats for its own
  audience. None of that is the filer's content, so it belongs in derived
  content, as a bound fact value beside a model left as filed.

`--alignInto model|derivedContent` states which, with the same semantics and the
same default (`derivedContent`) as `--taggingJournalInto`. Under
`derivedContent` the model is not touched at all — the output's `xbrlModel` is
byte-identical to the input's: each located fact value becomes a `basis: bound`
derived fact value carrying the pointer / offset / quote triple, and the
`derivedContent` object's own `reportSource` identifies the surface (a `url` and
a `factLocatorType`, self-contained, so recording where somebody else's facts
appear never adds a document to their model). Those entries carry **no `value`** —
aligning establishes *where* a fact appears, and the text found there is the text
the filing already states, so nothing was evaluated; the entry records the
location and the `transformation` / `scale` / `sign` by which it yields the value.

Implemented for the HTML5 surface. `--align-to-pdf` writes into the model only:
it emits two fact locator types (marked content, and a page region for chart
facts) and a derived content object names one source. Which of the two an
alignment writes into is `--alignInto`, and that choice is about who is running
the tool rather than about the data — see §4.

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
| **Generate** a tagged PDF from the HTML | [`tools/inlineXbrlToPdf.py`](tools/inlineXbrlToPdf.py) | No good PDF exists; you want a self-contained traceable PDF — the N-CSR case above |
| **Match** facts onto an existing tagged PDF | [`tools/alignFactsToSurface.py`](tools/alignFactsToSurface.py) | A filer/Acrobat PDF exists and looks better than anything rendered |
| **Match** facts onto an existing HTML5 document | [`tools/alignFactsToSurface.py`](tools/alignFactsToSurface.py) (`alignToHtml5`) | A published report carries no XBRL — the website case above |

All three consume the *html-locator* facts file produced by `saveOIMFacts`
(`--plugins saveOIMFacts --SaveOIMFactspace facts.json`), whose fact values carry
`xbrl:htmlElementId` locators, and rewrite those to the target surface's
locators: PDF page/MCID/bbox, or the `xbrlx:htmlElementPointer` /
`htmlTextOffset` / `htmlTextQuote` triple for HTML5.

The HTML5 target needs the triple rather than a bare pointer because a published
report has no per-fact elements to address: **27% of the numbers in Microsoft's
HTML5 annual report share an element with another number** (worst `<p>`: 14 of
them), so a pointer alone cannot say which number is the fact. The three
properties are collections, and fragment *i* is `pointer[i]` / `offset[i]` /
`quote[i]`.

All three directions are wired to `arelleCmdLine` (§4) and to the GUI Tools menu,
and all three also run as standalone scripts
(`python3 tools/alignFactsToSurface.py --html … --facts … --html5 …`).

---

## 2. Locator types

| Locator type | Properties | Resolves to | Produced for |
|---|---|---|---|
| `xbrl:pdfContentLocatorType` | `pdfPage` (int) + `pdfMcid` (int array) | marked-content glyphs | visible facts whose value fills their MCID(s) |
| `xbrl:pdfImageLocatorType` | `pdfPage` + `pdfBBox` (`"x0 y0 x1 y1"`) + optional `pdfImageHash` (`md5:…`) | a rectangular region | a chart **image**, or a sub-MCID text value's glyph box (see below) |
| `xbrl:pdfFormFieldLocatorType` | `pdfFormField` | an AcroForm field value | facts sourced from PDF form fields |
| `xbrl:htmlElementLocatorType` | `htmlElementId` | HTML element text | fallback for facts not located in the PDF |

Two further locator types address an HTML element that carries no `id`, and are
provisional — declared in `resources/xbrlx.json` under an `arelle.org` namespace
rather than an `xbrl.org` one, because they are implemented ahead of the
specification and naming them under xbrl.org would misrepresent their status:

| Locator type | Properties | Resolves to |
|---|---|---|
| `xbrlx:xhtmlPointerLocatorType` | `htmlElementPointer` (+ optional `htmlTextOffset`, `htmlTextQuote`) | an element of the **XML infoset** tree, and a character range within it |
| `xbrlx:htmlPointerLocatorType` | as above | an element of the **HTML5** tree |

`htmlElementPointer` is an XPointer `element()` child sequence written without the
`element(...)` wrapper — `currentAssets`, `/1/14`, `financial-review/2/1` — anchored
on an ancestor `id` where one is usable and counted from the root where not. It
exists because most real reports have almost nothing to address: Microsoft's
published annual report carries 42 `id` attributes across 8,383 elements, all
navigation anchors, so nothing in its 66 tables is addressable, and injecting ids
means rewriting a document that may be signed, checksummed, or simply not yours.

**The parse mode is part of the address, which is why there are two types.** An
element pointer counts element *children*, and the HTML5 tree-construction rules
(implied `<tbody>`, foster parenting) build a different tree from an XML parse of
the same bytes. On Microsoft's filed 10-K, which has 85 tables with no `tbody` in
source, only **6.8%** of pointers survive a parse-mode swap. So an emitter records
which tree it counted, and a consumer resolves in that mode or not at all. For the
same reason the aligner parses with lexbor (`selectolax`) and never `lxml.html`,
and `Html5Normalize.py` blanks `<noscript>` content before parsing — a browser
parses it as text when scripting is enabled, a bare parser as markup, and the
element counts then diverge.

**Two implementations must agree exactly, or they address different elements
silently.** [`HtmlElementPointer.py`](HtmlElementPointer.py) is a port of the
viewer's `tagging/elementPointer.js`; a disagreement produces a plausible wrong
element rather than an error. They are held together by a shared fixture corpus —
`iXBRLViewerPlugin/viewer/src/js/xbrlModel/tagging/corpus/` in the ixbrl-viewer
repository, SHA-pinned on both sides so neither can edit it unilaterally — which
both test suites run against.

The offset convention, where a value is part of an element's text rather than all
of it: `htmlTextOffset` is a 0-based character offset into that element's
`textContent` (all descendant text in document order, comments contributing
nothing), the value ends at `offset + len(quote)`, and text is never stripped or
whitespace-collapsed — collapsing belongs to the transform stage. A consumer
verifies the resolved text against `htmlTextQuote` and refuses to highlight on
mismatch, so a regenerated document is detected rather than silently
mis-addressed.

`pdfBBox` is in PDF user-space points, origin lower-left. For a **chart image**,
one region is typically referenced by many facts (see §3), so highlighting is
region-level, not per-value.

**Sub-MCID text values (hybrid content/bbox locator).** Accessibility tagging is
often *row-grained*: a whole table row — `TOTAL GROUPE 41 182,5 43 486,8 44 052,0
…` — is a single marked-content id, so a `pdfMcid` locator for one figure would
highlight the entire row. When a fact's value is only a **portion** of its MCID,
`alignFactsToSurface` instead emits a per-value `pdfBBox` — the glyph rectangle of
just that value, computed with pypdfium2 and disambiguated by the MCID row text —
carried on the image source (which viewers already render). A fact that *is* its
whole MCID(s) keeps the structural, reflow-robust `pdfMcid`. So for text a
`pdfBBox` is per-value; for a shared chart image it stays region-level. The bbox
is only emitted when its value is confidently placed (found within its row, or
unique on the page); otherwise the fact safely keeps its correct-row `pdfMcid`.

A small end-to-end fixture — source HTML, a chart image, a 1-page tagged PDF, and
an aligned factset that resolves all four PDF and HTML-element locator types — is the fastest way to
develop a consumer (viewer / resolver). One can be produced with `alignFactsToSurface`
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

### Model and viewer

See the quick start above for the worked example. The options:

| option | effect |
|---|---|
| `--saveOIMmodel <file>` | save the loaded model as one compiled model (`.json` / `.cbor` / `.xlsx`) |
| `--oimSaveMode full\|prune\|report` | how much to emit (§"Saving a model") — default `full` |
| `--saveXbrlModelViewer <dir>` | stage a servable viewer directory: model + source document(s) + viewer bundle |
| `--calcRoundingMode roundToNearest\|truncation` | override the model's declared rounding mode (§7) |
| `--xbrlModelStreamThreshold <n>` | fact count above which a fact source must stream |
| `--applyTaggingJournal <file>` | apply a tagging journal from the iXBRL Viewer's tagger (below) |
| `--taggingJournalInto model\|derivedContent` | where its bindings go — default `derivedContent` |
| `--taggingValueAuthority document\|value` | for `into model`: what the filing asserts is the point of truth — default `document` |
| `--align-to-pdf` / `--align-to-html5` | locate the facts of a tagged inline document in a second rendering (below) |
| `--alignInto model\|derivedContent` | where the located sources go — default `derivedContent` (HTML5 only; PDF is `model`) |

Both save options validate the model first (see the quick start). They run on the
`CntlrCmdLine.Xbrl.Run` hook, *after* validation — the earlier `Xbrl.Loaded` hook
runs before it, and saving from there wrote out a model whose facts had not yet
materialized.

### Applying a tagging journal

The iXBRL Viewer's tagger writes nothing to the model or the document. Its only output is a
**journal** of the value-source decisions a user made, and applying it is this step.

Which party is tagging decides what the resulting artifact claims, so `--taggingJournalInto`
states it rather than defaulting silently to one reading:

- **A preparer**, tagging a report they are authoring. The bindings are their own content — the
  filing says where its values come from — so `--taggingJournalInto model` puts them in the
  model, and the result is a filing with no derived content at all. This is the path for
  preparing a filing: import accounting data, let the tooling attempt the mapping to value
  sources, and tag what it could not place.
- **A disseminator**, tagging a report somebody else filed — re-rendering a prior filing onto a
  surface it was never tagged against, or locating values for a viewer.
  `--taggingJournalInto derivedContent` (the default) records them as derived fact values with
  a `basis` of `bound`, beside a model left exactly as filed. Nothing the filer did not report
  enters the model.

For a preparer, `--taggingValueAuthority` selects what the filing asserts is the point of truth
— a distinction the model already carries:

| | the fact carries | means |
|---|---|---|
| `document` (default) | `valueSources`, no value | the document text is authoritative; a consumer re-derives the value from it |
| `value` | `value` + `valueAnchors` | the value is authoritative — imported from an accounting system, a prior filing, a spreadsheet — and the binding only locates it |

A journal entry names its fact by the viewer's fact id. For a located fact that is
`<reportIndex>-<htmlElementId>` and resolves against the model; for one the viewer could not
locate, or placed on a PDF, it is a synthetic `hf-N` / `pf-N` — a position in the order the
adapter built, not an identity — and such an entry is reported unapplied rather than guessed
at. See [`ApplyTaggingJournal.py`](ApplyTaggingJournal.py).

### Diagnostics this plugin adds

Alongside the specification's `oimte:` / `oimce:` / `oime:` / `oimtc:` codes, the
plugin reports its own processing conditions under `arelle:`. The ones worth
recognising:

| code | means |
|---|---|
| `arelle:selfImportedTaxonomy` | a module imports a taxonomy of **its own name** — either it imports itself or two distinct modules share a name. The import cannot be resolved, and the whole closure would otherwise be dropped in silence |
| `arelle:calcNotCheckedNonNumericValue` | a calculation was **not checked** because a bound fact's value is not a number (commonly an untransformed value). Not an inconsistency — a calculation with no verdict |
| `arelle:calcRoundingModeOverridden` | `--calcRoundingMode` overrode the declared mode, so the results are not conformant results for the model as published |
| `arelle:xbrlModelViewerUnavailable` | no built viewer bundle was found — activate `iXBRLViewerPlugin`, or set `xbrlModelViewerBundleDir` |
| `arelle:xbrlModelViewerNoDocument` | the model names no source document, so there is nothing to render facts against (a taxonomy rather than a report) |
| `arelle:taggingJournalEntryUnresolved` | a journal entry named a fact the model does not locate — commonly a synthetic viewer id (see above) rather than an element id |
| `arelle:pocLegacyDtsNotDiscovered` | no XBRL 2.1 DTS was found at a referenced entry point |
| `arelle:factValueResolverFailed` | a fact value could not be resolved from its source document |

`arelleOIMloader:error` is different in kind: it reports that **validation was
abandoned** at that point, so no later check ran for the model. A model carrying
it has not been fully validated, however clean the rest of the log looks.

### PDF tools

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
- Writes into the model. `--alignInto derivedContent` is not supported here — see
  the HTML5 direction below.

### Match facts onto an existing HTML5 rendering

```bash
arelleCmdLine --plugins XbrlModel --align-to-html5 \
    --al-html report.xhtml --al-facts report-html-facts.json \
    --al-html5 annual-report.html --al-out-facts report-html5-facts.json \
    [--alignInto model|derivedContent]
```
- The target needs no XBRL and no `id` attributes: facts are located by an
  `xbrlx:htmlElementPointer` (XPointer `element()` child sequence, anchored on an
  ancestor `id` where one is usable) plus a text offset and quote.
- Parsed with lexbor (`selectolax`), never `lxml.html` — an element pointer counts
  element children of the **HTML5** tree, and an XML parse builds a different one.
- `--alignInto` says who is running it (§2). Default `derivedContent`: the model
  is left byte-identical and the locators become `basis: bound` derived fact
  values, the `derivedContent` object identifying the surface itself. `model`
  writes them onto the facts and declares the surface as a source of the model,
  for a preparer aligning onto their own site.

All three tools can also be run standalone (`python3 tools/<tool>.py --help`).

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
`CntlrCmdLine.Xbrl.Run` for the command line.)

The command-line save runs on the `Xbrl.Run` hook, *after* validation, and
validates the model first if nothing else has. Both matter: a legacy report opened
as an entry point materializes its DTS and facts at validate time, and the saved
model is meant to carry validation verdicts. Saving from the earlier `Xbrl.Loaded`
hook wrote out an empty model and reported success.

### Derived content

A saved compiled model carries a `derivedContent` object — a document-level sibling of
`documentInfo` and `xbrlModel`, **not part of the model** — holding what processing computed
rather than what the filer reported:

| | |
|---|---|
| `factValues` | the values resolved from each fact's value sources, with `basis: resolved` |
| `cubeContents` | which fact objects match each cube |
| `calculationResults` | what validation concluded for each calculation binding |
| `derivation` | when, by what processor, under which rule sets — required wherever non-derivable content is carried |

On Microsoft's FY2025 10-K: 1,827 derived values, 113 cube contents over 4,569 (cube, fact)
pairs, and 184 calculation results — 163 consistent, 21 not. The 163 are the ones nothing
reports today, and are the reason to carry results rather than only errors.

**A fact no longer carries a derived value.** In `full` and `prune` modes, a fact whose value
was resolved from its value sources keeps its faithful form — sources, no value — and the
resolved value is published as derived content. Emitting it on the fact made a value the
processor computed indistinguishable from one the filer reported, which is what derived content
exists to prevent. `report` mode is unchanged: it deliberately makes the value the single
source of truth for a viewer that reads one, so the value stays on the fact and `factValues` is
omitted rather than saying the same thing twice.

An unvalidated model derives nothing and emits no derived content, which is the correct reading
rather than a gap: absence means "not published, derive it yourself" for derivable content, and
for a calculation result asserts neither consistency nor that anything was checked.

**Why a verdict is carried rather than recomputed when the report is read.** Validation on
receipt is a statement about a moment: this is what the rules concluded, then. Revalidating at
viewing time answers a different question, because standards, rules and implementations move
between receipt and reading — so the same artifact would report differently over the years,
with nothing recording which reading was authoritative or when it changed. For a disseminated
artifact that is a misrepresentation of what was filed and accepted, not a fresher opinion.
Production intake validates on receipt and carries the verdict; EDGAR works this way.

Both profiles stay legitimate, which is why emitting results is a step rather than a mode the
product is in: a desktop user opening a filing they just downloaded has no receipt event and no
carried verdict, and validating locally is the right thing for them.

What this asks of a consumer is that **three states stay distinguishable** end to end —
validated and consistent, validated and inconsistent, and *not validated*. A model carrying no
result must not be presented as though it carried a clean bill, which is what a silent local
recompute would produce, since it would look identical to a carried verdict. It is the same
silent-wrong-answer shape as a mis-placed locator: a plausible result and a correct one,
indistinguishable to the reader.

Specified in `oim-taxonomy-derived.md` in the `oim` repository, with a JSON schema alongside it;
validate a model carrying derived content against `oim-taxonomy-derived-document-schema.json`,
since the taxonomy schema closes its document root. See
[`SaveModel.buildDerivedContent`](SaveModel.py). What a consumer does with it is documented on
the other side, in `iXBRLViewerPlugin/viewer/src/js/xbrlModel/README.md` ("Derived content") in
the ixbrl-viewer repository.

### Opening a model in the iXBRL Viewer

The last step of the desktop workflow — see the *document surface* the facts were
located in, with the report's own facts bound to it. A compiled model does not go
through the iXBRL Viewer plugin's own launch (which builds a viewer *document* from
a legacy inline report); it uses the viewer's XbrlModel overlay, which takes a plain
document plus an OIM model.

- **Automatic on load**, when the model has a source document *and* facts located in
  it. **Tools ▸ "Open iXBRL Viewer on load"** turns that off.
- **Tools ▸ "View XBRL model in iXBRL Viewer"** opens the loaded model on request.
- **`--saveXbrlModelViewer <dir>`** (command line) stages the same directory without
  opening a browser, for serving elsewhere.

Either way the staged directory is self-contained: the compiled model, the source
document(s), and the viewer bundle. The model's `documentInfo.sourceMappings` is
rewritten to name the staged document, so the viewer resolves it from the model.

The directory follows Arelle's existing convention (as `EDGAR/render` does): a
subdirectory named `out` beside the entry file — or beside the *archive*, when the
entry file is inside a zip, report package or taxonomy package — falling back to the
web cache directory for that URL and then to a temp directory. Configurable with
`xbrlModelViewerFolder`.

The viewer bundle (`viewer/dist/ixbrlviewer.js` and its code-split chunks) is found
from a loaded `iXBRLViewerPlugin`, from the plugin configuration's `moduleURL`, or
from the `xbrlModelViewerBundleDir` config key. Without a built bundle the launch
reports `arelle:xbrlModelViewerUnavailable` rather than opening an empty window.
See [`ViewerLaunch.py`](ViewerLaunch.py).

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
- **HTML5 *source* documents are a different question.** The note above is about
  *rendering* inline XBRL, which must stay in XML mode. Locating facts in a plain
  HTML5 presentation document is the opposite direction, and there the HTML5
  tree-construction algorithm is mandatory: it synthesizes `<tbody>`,
  foster-parents stray table content and implies `<head>`, so child indices and
  ancestry differ from an XML parse. Arelle uses lexbor (`selectolax`) and copies
  its tree into lxml directly — serialising and re-parsing is only ~91%
  structurally faithful, and both failure modes (quirks mode, adoption agency)
  are silent. There is deliberately no fallback to `lxml.html`: a plausible value
  from the wrong element is worse than no answer.
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

### What the legacy translation carries

[`LoadLegacyTaxonomy.py`](LoadLegacyTaxonomy.py) turns a discovered XBRL 2.1 DTS
into a compiled model. Two properties of that translation are worth knowing
because they show up in the emitted names and in what survives:

* **Arcroles other than presentation and calculation are carried too.** Each one
  becomes a `relationshipType` object plus a network per linkrole, taking the
  **canonical name** where a built-in model declares it (`core.json` declares the
  LRR deprecation arcroles as `xbrl:dep-*`, so those resolve to the same objects
  every other model uses) and a synthesised one otherwise. Without this an ESEF
  filing's anchoring — the ESMA `wider-narrower` arcrole the RTS requires for
  every extension concept — was dropped in silence, because it has no
  presentation or calculation meaning. The known-name map is read from the
  shipped resources, so declaring an arcrole in a spec taxonomy is picked up
  here automatically and replaces the synthesised name.
* **Synthesised names carry a digest when abbreviated.** Group, cube and network
  names derive from extended-link role URIs, which SEC filers make long and
  highly similar — `…OfferingsDetail` and `…OfferingsParentheticalDetail` agree
  for the first 60 characters. A name that fits is used unchanged; one that must
  be abbreviated gets a digest of the full name appended, because truncation
  alone silently merges two distinct presentation groups into one.

---

## 7. Calculation validation

Summation-concept (calculation) relationships are validated per
`specifications/oim-taxonomy/summation-item-relationship-proposal.md`, whose
consistency-checking semantics are those of [Calculations 1.1][calc11]:

* **Definition-time checks** (proposal §5), in [`ValidateNetworkObjects.py`](ValidateNetworkObjects.py):
  numeric (decimal-derived) concepts, matching `periodType`, the balance/weight/reconciliation
  table, no duplicate total→contributing pair, and every concept in the associated cube's
  concept domain.
* **Binding and consistency checking** (proposal §6.2 and §7), in
  [`ValidateCalculations.py`](ValidateCalculations.py): a calculation binds only against the
  facts of a cube that lists its network in `cubeNetworks`, and is checked with interval
  arithmetic. The same module checks **greater-lesser** orderings (proposal §11), which
  assert that one concept's reported value cannot exceed another's at the same dimensional
  position — gross carrying amount and net, or a total and an "of which" part. The intervals themselves reuse `rangeValue()` and `insignificantDigits()` from
  [`arelle/ValidateXbrlCalcs.py`](../../ValidateXbrlCalcs.py), which is what keeps this and
  Arelle's Calculations 1.1 implementation in step.
* **Legacy translation** (proposal appendix B), in [`LoadLegacyTaxonomy.py`](LoadLegacyTaxonomy.py):
  an XBRL 2.1 calculation linkbase becomes summation-concept networks, associated with a
  generated all-facts cube so they bind against the whole report as they did under
  Calculations 1.1.

Errors use the proposed `oimtc` namespace, registered in
[`resources/oimtc.json`](resources/oimtc.json).

### Rounding mode, and overriding it at run time

The rounding mode is a property of the model or the network (`xbrl:roundingMode`, proposal
§3), not a processor setting, so a calculation is checked the same way by every processor.
It defaults to `roundToNearest`; `truncation` gives the half-open intervals used where
amounts are truncated rather than rounded.

The proposal permits a processor to override the declared mode at run time (§3.3) — for a
report whose rounding convention is known out of band, or to run a conformance suite that
parameterises the mode per variation:

```bash
arelleCmdLine --plugins XbrlModel --validate --file report.json \
    --calcRoundingMode truncation
```

Accepted values are `roundToNearest` and `truncation`. When the override differs from the
declared mode, `arelle:calcRoundingModeOverridden` is reported: as the proposal requires,
results obtained under an override are **not** conformant results for the model as published.

### Running the Calculations 1.1 conformance suite

The XBRL International Calculations 1.1 suite is the check on the interval arithmetic, since
it exercises truncation, excess digits and duplicate handling, which the OIM taxonomy suite
does not. Its instances name their taxonomy (`documentInfo.taxonomy` for xBRL-JSON,
`link:schemaRef` for XBRL 2.1), which is compiled on demand, so a variation runs directly:

```bash
arelleCmdLine --plugins XbrlModel --validate \
    --file calc11/excess-digits-on-total-instance.json
```

Its `index.xml` carries the expected result and a `calc11conf:mode` of `round-to-nearest`
or `truncate` per variation; map each expected `calc11e:`/`oime:` code to its `oimtc:`
counterpart using the "Origin" column of §10 of the proposal, and pass
`--calcRoundingMode truncation` for the truncate variations.

66 of the suite's 68 variations produce exactly the specified codes. The two exceptions are
the `oim-illegal-fraction-item` pair, where Calculations 1.1 declares the report
OIM-incompatible and skips checking entirely; here the fraction concept's datatype does not
resolve, which is reported as `oimte:invalidQNameReference`, and the fraction fact then does
not contribute, so the total is additionally reported as inconsistent.

[calc11]: https://www.xbrl.org/Specification/calculation-1.1/REC-2023-02-22+corrected-errata-2024-02-14/calculation-1.1-REC-2023-02-22+corrected-errata-2024-02-14.html

## 8. Files

| File | Role |
|---|---|
| [`tools/inlineXbrlToPdf.py`](tools/inlineXbrlToPdf.py) | generate a tagged PDF (Chrome/WeasyPrint), token carrier, reflow |
| [`tools/alignFactsToSurface.py`](tools/alignFactsToSurface.py) | match facts onto a second rendering — PDF or HTML5 (row-granular signature match → token patience-align → phrase-locate → image pairing) |
| [`Html5Normalize.py`](Html5Normalize.py) | pre-parse normalization of HTML5 bytes so Arelle's tree matches the browser's (`<noscript>` content) |
| [`HtmlElementPointer.py`](HtmlElementPointer.py) | XPointer `element()` child sequences — generate, resolve, verify (port of the viewer's `elementPointer.js`) |
| [`PdfTextExtractor.py`](PdfTextExtractor.py) | tagged-PDF text by mcid / struct-id / form field (page-scoped) |
| [`PdfToolsCli.py`](PdfToolsCli.py) | command-line options + dispatch (wired from `__init__.py`) |
| [`FactValueResolver.py`](FactValueResolver.py) | resolves html / pdf locators to source text during validation |
| [`ValidateCalculations.py`](ValidateCalculations.py) | summation-concept binding and consistency checking (proposal §6.2, §7) |
| [`ValidateNetworkObjects.py`](ValidateNetworkObjects.py) | network validation, including the summation-concept definition-time checks (proposal §5) |
| [`LoadLegacyTaxonomy.py`](LoadLegacyTaxonomy.py) | legacy XBRL 2.1 DTS → compiled model, including calculation linkbases and the all-facts cube (proposal appendix B) |
| [`ViewerLaunch.py`](ViewerLaunch.py) | stage a self-contained iXBRL Viewer directory (model + document + bundle) and open it |
| [`tools/genSecTransformTypes.py`](tools/genSecTransformTypes.py) | regenerate `resources/sec-transform-types.json` from SEC's formal transformation registry |
| [`loadFromPDF.py`](../loadFromPDF.py) | read a tagged PDF + template into facts (the reverse, standalone PoC) |

Spec: locator property types and fact locator types are defined in
`specifications/oim-taxonomy/oim-taxonomy.md`.
