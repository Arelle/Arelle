# Handover: getting a legacy filing to a viewable XbrlModel

For the session taking on the end-to-end workflow — legacy DTS and instance in,
something the ixbrl-viewer can open out.

Written 2026-08-21 by the tagger session, which needed this working to build the
Microsoft three-surface demo and learned it by hitting the walls. Everything
below is measured on that filing rather than read from the code, so treat the
failures as symptoms to explain, not as diagnoses.

---

## 1. What "viewable" means

`iXBRLViewer.loadXbrlModel` (`ixbrlviewer.js`) accepts either shape:

| shape | what it is | needs a taxonomy? |
|---|---|---|
| **compiled model** | taxonomy structures *and* facts in one document | no |
| **factset** | facts only; the taxonomy is resolved separately | yes |

and a plain document to render. The viewer URL takes all three:

```
?xbrlModel=<facts-or-model>[&taxonomy=<model>]&document=<document>
```

A config block may name them instead (`factset`, `taxonomy`, `document`), and the
comment at `ixbrlviewer.js:470` says the document and taxonomy URLs are otherwise
resolved from the factset's own `documentInfo` (`sourceMappings` +
`importMapping`) relative to the factset. That resolution is what §3.1 below does
not appear to do.

**Without a taxonomy there are no cubes**, and the Cubes tab hides. That is a
property of the artifact, not of the filing — see §3.1.

## 2. What works, with measured output

Microsoft FY2025 10-K throughout; artifacts in `/Users/hermf/temp/pdf/Microsoft/`.

### 2.1 Facts out of a filing

```bash
arelleCmdLine --plugins saveOIMFacts --internetConnectivity online \
    --file 0000950170-25-100235-xbrl.zip --SaveOIMFactspace msft-facts.json
```

`loaded in 5.80 secs`, 1.38 MB, **1,708 facts**, 1,800 `xbrl:htmlElementId`
locators. Arelle reads the EDGAR filing ZIP directly and finds the entry point
inside it.

The only errors are `ix11.11.1.2:invalidTransformation` for SEC's 2015
transformation namespace, which are benign here.

Note what a factset is:

```json
"importedTaxonomies": [{"xbrlModelName": "msft:msft-20250630"}],
"importMapping":      {"msft:msft-20250630": "msft-20250630.xsd"},
"sourceMappings":     [{"sourceName": "msft:msft-20250630Source", "url": "msft-20250630.htm"}]
```

It **names** the DTS; it does not contain it. Collections present:
`importedTaxonomies, factSources, factMaps, facts, footnotes`. No concepts, no
cubes, no groupTree.

### 2.2 A taxonomy out of the DTS

Extract the extension schema from the ZIP first — `importMapping` is a relative
path, so it must sit beside whatever loads it.

```bash
arelleCmdLine --plugins XbrlModel --internetConnectivity online \
    -f msft-20250630.xsd --saveOIMmodel msft-dts-model.json --oimSaveMode full
```

4.27 MB, and the legacy loader infers the structures:

```
cubes 123 · concepts 12,488 · networks 117 · groups 129 · groupTree yes
```

Cube names come out as `msft:group_DisclosureComponentsOfLongtermDebtDetail_Cube`,
so this is `LoadLegacyTaxonomy`'s presentation/definition inference doing its job
on an ordinary SEC filing.

It emits `oimte:duplicateItemsInSet` on some inferred domain networks and still
writes the model. Worth understanding before relying on it, but not fatal.

### 2.3 Pairing them for the viewer

```
?xbrlModel=msft-facts.json&taxonomy=msft-dts-model.json&document=msft-ar25-html5.html
```

Cubes panel: **24 sections, 112 cubes**. Verified on all three Microsoft
surfaces (inline filing, HTML5 report, PDF).

### 2.4 What the DTS needs to resolve

- The **extension schema** must be local and keep its filename. It is in the
  EDGAR filing ZIP (`msft-20250630.xsd`, 2 MB, linkbases embedded).
- `us-gaap` (xbrl.fasb.org), `dei` and `ecd` (xbrl.sec.gov) fetch fine — all
  three returned 200 and were **not** in the Arelle web cache, so a first run
  downloads them and is slower.
- `www.sec.gov/Archives` serves Arelle **fine**. `WebCache.py` sends a declared
  User-Agent in SEC's required product-plus-contact form, defaulting to
  `Mozilla/5.0 (Arelle/<version>) Email/NotRegistered@arelle.org`, overridable
  with `--httpUserAgent`. Verified: `webCache.getfilename()` on
  `msft-20250630.xsd` returns all 2,066,295 bytes and caches them under
  `~/Library/Caches/Arelle/https/www.sec.gov/...`.

  So **a workflow step should retrieve through `WebCache`, never through an
  ad-hoc fetch.** A bare `curl` is what gets "Your Request Originates from an
  Undeclared Automated Tool", which is why the files for this work were
  downloaded by hand -- avoidable, and not a constraint on the workflow. Anyone
  running it against real filings should set `--httpUserAgent` to a real
  address rather than leave it as `NotRegistered@arelle.org`.

## 3. What does not work

Two failures, which may well be one thing.

(An earlier draft listed a third, "EDGAR blocks automated retrieval". That
was wrong -- it blocked a raw curl, not Arelle. See §2.4.)

### 3.0 What has since been fixed nearby (2026-08-29)

A *report entry point* — an xBRL-JSON or xBRL-CSV instance, or an XBRL 2.1 `.xml`
instance, given directly as the file to load — now does pull in its taxonomy.
It previously did not, for the same visible symptom as §3.1: facts materialized
but no concept, cube or network they refer to was ever compiled.

Three causes, all fixed in `575e25ad1`:

* `pocCompileLegacyDts` was handed the **report's own URL**, which resolves to no
  DTS for a JSON document. `_reportTaxonomyUrls` in `FactPipeline.py` now follows
  what the report *names* — `documentInfo.taxonomy`, or `link:schemaRef`.
* The failure was invisible: the call sits inside `except Exception: pass`.
* A module compiled on demand is appended to `xbrlModels` **after**
  `validateCompiledModel`'s loop has passed its position, so it escaped
  definition-time validation entirely. That loop now repeats until no new module
  appears.

This does **not** fix §3.1, which was re-tested on 2026-08-29 and is unchanged:
`msft-facts.json` still produces 0 cubes / 0 concepts / 1,708 facts with the same
`invalidQNameReference` on a built-in locator type. §3.2 is likewise unchanged
(0.10 s, empty model). The two paths are different mechanisms — a *factset*
resolves its taxonomy through `importedTaxonomies` / `importMapping`, not through
a factSource bound to a built-in fact map — so §3.1 remains the open question.

What it does narrow: the fact-map side of the family is now known-good and can be
used as a working comparison. Loading the calc11 conformance suite's
`excess-digits-on-total-instance.json`, whose `documentInfo.taxonomy` names
`calc.xsd`, compiles that DTS, binds its calculation networks and reports an
inconsistency — the whole chain the factset path fails to complete.

### 3.1 A factset does not pull in its own DTS

```bash
arelleCmdLine --plugins XbrlModel -f msft-facts.json \
    --saveOIMmodel out.json --oimSaveMode report      # and --oimSaveMode full
```

Both modes produce **0 cubes, 0 concepts, 1,708 facts** — the factset re-emitted.

Ruled out:

- **Not the DTS.** The same `msft-20250630.xsd` compiles to 123 cubes as its own
  entry point (§2.2).
- **Not a missing file.** The `.xsd` was extracted beside the factset, so the
  relative `importMapping` path resolves on disk.
- **Not pruning.** `full` mode behaves the same as `report`.

In `report` mode it also emits, for every fact:

```
oimte:invalidQNameReference ... factLocatorType xbrl:htmlElementLocatorType
    does not resolve to any factLocatorType object
```

`xbrl:htmlElementLocatorType` is a **built-in** from `core.json`, so the model's
import closure is not being assembled at all, not merely the extension DTS. In
`full` mode that error disappears while the emptiness remains, which is itself a
clue.

This is the one that matters most: it is the difference between a two-file
pairing and a single self-contained model, and the CLI docs describe the
single-file outcome as the intended one.

### 3.2 The inline entry point claims and then does nothing

```bash
arelleCmdLine --plugins XbrlModel -f msft-20250630.htm --saveOIMmodel out.json
```

Returns in **0.12 s** with an empty model. A plain Arelle load of the same file
takes **6.67 s** and produces facts.

The plugin does claim it — `__init__.py:1292` calls `pocReportEntryFactMap` for
inline XBRL 1.1 `.htm`/`.xhtml`, and `xbrlModelLoader` dispatches to
`pocLoadReportAsEntry`. So the claim fires and the load produces nothing.

Same behaviour when pointed at the filing ZIP.

## 4. The workflow does not end at "viewable"

The viewer is not only a renderer: its tagging mode emits a **journal** of the
value-source decisions a user made, and that has to come back into the factset.
Nothing currently does that, and it is the piece that closes the loop.

The journal is the tagger's only output. Nothing is written to the model or the
document from the browser, deliberately -- so the non-mutation invariant is
mechanically true rather than merely intended, and applying the journal is a
separate step that belongs on the Arelle side.

Its shape (`ixbrl-viewer/.../xbrlModel/tagging/journal.js`, and TAGGER.md §4):

```json
{
  "journalVersion": 1,
  "document": "msft-ar25-html5.html",
  "model": "msft-facts.json",
  "entries": [
    {
      "op": "bindValueSource",
      "factId": "0-pf-0",
      "previous": null,
      "locatorType": "xbrlx:htmlPointerLocatorType",
      "sources": [{ "properties": [
        { "property": "xbrlx:htmlElementPointer", "value": ["shareholder-letter/3/3"] },
        { "property": "xbrlx:htmlTextOffset",     "value": [81] },
        { "property": "xbrlx:htmlTextQuote",      "value": ["15"] }
      ]}],
      "derivation": { "scale": 6 },
      "capturedText": "15",
      "factValue": "15",
      "verdict": "agree"
    }
  ]
}
```

Four things an applier needs to honour, each of which the producer side already
depends on:

- **`sources` is already in `factValueSourceObject` form**, so applying an entry
  is an attach, not a translation. Its arrays are parallel and collection-typed:
  fragment *i* is `pointer[i]` / `offset[i]` / `quote[i]`.
- **`previous` makes an entry reversible** -- null for a first bind, the
  displaced sources for a rebind -- without consulting the model.
- **`capturedText`, `factValue`, `verdict` and `derivation` are provenance, not
  instructions.** They let a reviewer see why a binding was accepted without
  re-running the tool, and let an applier warn if the document has changed since.
  A `verdict` of `differ` is not an error: scaling, sign and locale formatting
  all make a value legitimately differ from its presentation.
- **Entries are per user decision, not per model mutation.** Binding a value and
  saying how it derives is one decision and one entry.

`op` is `bindValueSource` throughout today. The field exists so the vocabulary
can grow — `addConcept`, `addMember` — once object creation is in scope; it was
deliberately left at one value until then.

The natural home is a CLI step alongside the others: journal in, updated factset
out, with validation. That would make the round trip complete —
filing → factset → viewable → tagged → factset — which is the workflow this
handover is really about.

## 5. Artifacts to work against

`/Users/hermf/temp/pdf/Microsoft/` — full characterisation in its `FINDINGS.md`.

| file | |
|---|---|
| `0000950170-25-100235-xbrl.zip` | the EDGAR filing: instance + 2 MB extension schema |
| `msft-20250630.xsd`, `msft-20250630.htm` | extracted from it, needed for relative resolution |
| `msft-facts.json` | §2.1 output, 1,708 facts |
| `msft-dts-model.json` | §2.2 output, 123 cubes |
| `msft-facts-pdf.json` | after `alignFactsToPdf`, 1,525 of 1,800 located |
| `msft-ar25-html5.html`, `msft-fy25-10k.pdf` | the other two surfaces |

L'Oréal is the contrast case: its demos use **compiled models**
(`loreal-complete.json`, 10 cubes / 3,772 concepts / groupTree in one file) and
need no separate taxonomy. Whatever produced those is the shape §3.1 is trying
and failing to reach; that provenance is not recorded here and is worth
recovering — `project_complete_model_cli` in memory describes a
"facts-only aligned-facts module (importMapping→legacy DTS) → prune →
self-contained compiled model" flow with a paclife proof, which sounds like
exactly §3.1 working.

The viewer demo set and its URLs are in
`ixbrl-viewer/iXBRLViewerPlugin/viewer/demo-xbrl-model/README.md` (untracked,
because most of what it documents is untracked working material).

## 6. Suggested order

1. **§3.1 first.** It is the highest-value unblock and the most diagnosable: a
   working single-file compile removes the two-file pairing everywhere.
   The `invalidQNameReference` on a *built-in* locator type is the thread to
   pull — the closure is not being assembled, so the question is what assembles
   it when a `.xsd` is the entry point and does not when a factset is.
2. **Recover how the L'Oréal compiled models were made.** If that path still
   works, comparing it against §3.1 localises the difference quickly.
3. **§3.2**, which may fall out of the same fix.
4. Then the workflow proper: one command from filing to viewable, whatever
   sequence that turns out to be.
5. **The journal applier** (§4), which closes the loop. Independent of 1--3 and
   could be done first if a demonstrable round trip is worth more than a tidy
   single-file compile; the journal format is settled and has a working producer.
