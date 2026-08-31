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

## 3. What did not work, and why — all resolved 2026-08-29

Both failures are fixed. They were unrelated to each other and neither was in the
mechanism the earlier draft suspected: the import closure and the report entry
point both worked, and were defeated by a name collision and a hook ordering.

Regression check: the OIM taxonomy conformance suite is **725 pass / 31 fail,
byte-identical before and after** these changes (756 variations).

### 3.0 What was fixed nearby (earlier the same day)

A *report entry point* — an xBRL-JSON or xBRL-CSV instance, or an XBRL 2.1 `.xml`
instance, given directly as the file to load — now pulls in its taxonomy.

Three causes, all fixed in `575e25ad1`:

* `pocCompileLegacyDts` was handed the **report's own URL**, which resolves to no
  DTS for a JSON document. `_reportTaxonomyUrls` in `FactPipeline.py` now follows
  what the report *names* — `documentInfo.taxonomy`, or `link:schemaRef`.
* The failure was invisible: the call sits inside `except Exception: pass`.
* A module compiled on demand is appended to `xbrlModels` **after**
  `validateCompiledModel`'s loop has passed its position, so it escaped
  definition-time validation entirely. That loop now repeats until no new module
  appears.

### 3.1 A factset did not pull in its own DTS — a name collision

`saveOIMFacts` named the facts module after the **report document's** basename
stem, and each imported taxonomy after **its own** document's stem. On EDGAR
those are the same string: the instance is `msft-20250630.htm` and the extension
schema is `msft-20250630.xsd`. So the factset came out naming itself
`msft:msft-20250630` *and* importing `msft:msft-20250630`.

The import-cycle guard in `loadXbrlModule` — added so the legitimately cyclic
built-in models (`xbrlm:base` ↔ `utr` / `iso4217` / `xbrla`) do not re-descend —
saw an edge to a name already on the loading path and skipped it. Its assumption,
sound for a real cycle, is that the target's objects arrive anyway because the
target is the ancestor. Here the two names denoted **different documents**, so
nothing arrived: not the DTS, and not even `xbrlm:base`, which is why a
*built-in* locator type failed to resolve.

That was the thread §7 said to pull, and it led to the producer, not the loader.

Fixed on both sides:

* **Producer** (`saveOIMFacts.py`): the facts module is suffixed `Facts` when its
  name would collide with a taxonomy it imports — `msft:msft-20250630Facts`.
* **Consumer** (`XbrlModel/__init__.py`): a module importing **its own name** is
  no longer treated as a cycle to skip. It cannot be one — either a module
  imports itself, or two distinct modules share a name — so it is reported as
  `arelle:selfImportedTaxonomy` instead of silently dropping the whole closure.

Measured, on the same filing:

```bash
arelleCmdLine --plugins saveOIMFacts --internetConnectivity online \
    --file 0000950170-25-100235-xbrl.zip --SaveOIMFactspace msft-facts.json
arelleCmdLine --plugins XbrlModel --internetConnectivity online \
    -f msft-facts.json --saveOIMmodel msft-complete.json --oimSaveMode full
```

8.4 MB, **12,488 concepts · 124 cubes · 141 networks · 129 groups · groupTree ·
1,708 facts**, in 5.5 s. One self-contained file; no separate `&taxonomy=`.

### 3.2 The inline entry point claimed and then did nothing — hook ordering

Two causes, stacked.

1. A report entry point materializes its DTS and facts at **validate** time
   (`FactPipeline.materializeFactSourceFacts`, called from `validateXbrlModule`).
   The CLI does not validate unless `--validate` is given, so the load really did
   produce nothing — in 0.10 s, as observed.
2. Passing `--validate` was still not enough, because `--saveOIMmodel` was
   emitted from the **`CntlrCmdLine.Xbrl.Loaded`** hook, which runs immediately
   after loading and **before** validation (`CntlrCmdLine.py:2054` vs `:2112`).
   The save therefore serialized the un-materialized model and logged success.

Fixed by moving the save to a new **`CntlrCmdLine.Xbrl.Run`** hook
(`xbrlModelRun`), which runs after validation, and by making `--saveOIMmodel`
validate the model if nothing else has. That last part is a deliberate policy,
not a convenience: an artifact whose stated purpose is to carry value sources and
validation verdicts (§5) cannot be produced from an unvalidated model. It matches
the GUI, which validates on load by default.

Measured — one command, filing to complete model:

```bash
arelleCmdLine --plugins XbrlModel --internetConnectivity online \
    -f 0000950170-25-100235-xbrl.zip --saveOIMmodel msft-model.json
```

8.9 MB, **12,488 concepts · 124 cubes · 145 networks · groupTree · 1,829 facts**,
in 5.7 s. 1,827 of the 1,829 factValues carry an `xbrl:htmlElementId` value
source, and `documentInfo.sourceMappings` binds the source document. Pointing at
the extracted `.htm` instead of the ZIP gives the same result.

### 3.3 A crash that was hiding behind them

`ValidateCalculations._factValueInterval` assumed every bound fact value parses
as a number. `rangeValue` returns a `Decimal` NaN when it does not, and the
ordered comparison that follows **raises** rather than returning an interval —
`decimal.InvalidOperation`, caught by `xbrlModelValidator`'s blanket handler,
which aborted `validateCompleteReportCubes` for the whole model.

On this filing one fact triggered it: `us-gaap:CommercialPaper` with
`transformation: ixt-sec:numwordsen` and the raw text `"no"`. Arelle without the
EDGAR plugin does not recognize SEC's 2015 transformation namespace
(`ix11.11.1.2:invalidTransformation`), so the transform is not applied and the
**untransformed text is kept as the value**.

The interval function now returns a `nonNumeric` status, and `_checkBinding`
reports `arelle:calcNotCheckedNonNumericValue` naming the concept and stops
checking that calculation. Skipping it silently was the alternative and is worse:
a calculation nobody could check would have been indistinguishable from one that
passed. Validation now completes (3.54 s) and reports 21 calculation
inconsistencies where it previously reported none and aborted.

**Left open, deliberately:** an inline fact whose transformation cannot be
applied keeps its raw text as though that were the value. Carrying no value —
leaving the factValue in Form A with its `valueSources` — would say what is
actually known. Same shape as everything else here: a plausible answer and a
correct one are indistinguishable to the reader.

### 3.4 Four defects that only opening the viewer would find

The compiled model produced above loaded into the viewer, resolved its taxonomy,
rendered the document — and located **no facts at all**. Each cause produced an
artifact that looked right by every measure short of using it.

1. **`xbrl:htmlElementId` was serialized as a string, not a collection.** Its
   declared type is `xbrlr:stringCollection` (`resources/core.json`), and
   `saveOIMFacts` emits `["F_..."]`; `LoadInlineFacts` emitted `"F_..."`. A
   consumer that spreads the collection — the viewer adapter does — then gets
   one "id" per character and matches nothing. Fixed in `LoadInlineFacts`.
2. **Validation replaces `factDimensions["xbrl:unit"]` with the parsed
   `(numerators, denominators)` tuple** it checked (`ValidateFacts`,
   `parseUnitString`). Saving after validation — which §3.2 made the norm —
   emitted the Python repr `"((iso4217:USD,), ())"` where the OIM string
   `"iso4217:USD"` belongs. `SaveModel` now writes the unit string back
   (`unitDimensionString`, the inverse of `parseUnitString`).
3. **Validation also caches `_periodValue` inside `factDimensions`**, and that
   internal key was serialized beside the real dimensions. A consumer that reads
   unrecognized keys as taxonomy-defined dimensions gives every fact a dimension
   it does not have. `SaveModel` skips underscore-prefixed keys.
4. **A report loaded from an archive resolved no fact values at all.** Its
   sourceMapping is bound to the *archive* — deliberately, so the report
   package's catalog remappings apply and the whole IXDS is discovered — and an
   archive cannot be read as a document. Every value was therefore "deferred",
   which is silent by design. `FactPipeline.reportDocumentUrls` now yields the
   document(s) the entry point actually named (expanding an inline-document-set
   surrogate URL), and both `FactValueResolver` and the viewer staging use it.

Only the first showed up as a difference between a working artifact and a broken
one; the other three were found by comparing a model that bound facts against one
that did not, field by field. An argument for keeping a rendering check in the
loop: none of the four changed any conformance result, and the suite is 725/756
either way.

### 3.5 An abandoned validation reads exactly like a clean one

Extending a *domain* network whose base declares no relationships raised
`AttributeError: 'NoneType' object has no attribute 'add'`
(`ValidateXbrlModel.py`, the `extendTargetObj.relationships.add(relObj)` line).
`relationships` is `Optional[NonemptySet]`, so an absent set is `None`, not empty
— the same guard has existed for `XbrlNetwork` in `ValidateNetworkObjects.py`
since that path was written; the domain-network path never got it. Fixed.

The more important half is what the failure looked like. `xbrlModelValidator`
catches every exception, logs one line and returns, so validation of the **whole
model** was abandoned at that point — no cube completeness, no calculations,
nothing after it — and the caller still reported `validated in 0.10 secs`. That
is the third time in this work a blanket handler has turned an abort into
something indistinguishable from a completed pass (see §3.3, and §3.0's
`except Exception: pass`).

The handler now says `Validation ABANDONED (no further checks ran for this
model)` and sets `_xbrlModelValidationAbandoned` on the model. That flag is the
third state §5 point 4 requires, and the emit step (§5) should carry it: a model
whose validation did not finish must not be published as validated.

### 3.6 What the first GUI run turned up

The Microsoft filing opened, rendered and selected facts in the viewer on the
first GUI attempt. The log around it was the problem, and it hid two real
defects.

**A single message was ~50,000 characters.** A JSON-schema validator reports a
violation by quoting the offending *instance*, so a `uniqueItems` violation on
`domainNetworks` quoted every domain network in the model — one log line that
buried the ~150 messages around it. `schemaErrorMessage` now truncates any
schema message, and for a duplicate-items violation replaces it entirely with
the far more useful thing the validator does not report: **which** items collide,
computed from the instance (`schemaErrorDuplicates`).

That immediately named the second defect. `_safeLocal` truncated a synthesised
name to 60 characters, and truncation is not injective — SEC role names differ
late:

```
Role_DisclosureRevenueClassifiedBySignificantProductAndServiceOfferingsDetail
Role_DisclosureRevenueClassifiedBySignificantProductAndServiceOfferingsParentheticalDetail
```

Both collapsed to one name, and so did
`…SummaryOfChangesInAccumulatedOtherComprehensiveIncomeLossByComponent{,Parenthetical}Detail`.
Two distinct presentation groups were silently merged, and the merge surfaced
only as `duplicateItemsInSet` and four `duplicateLabelObject` errors. A name that
still fits is left alone; one that must be abbreviated now carries a digest of
the full name. Domain networks 217 → 218 (the collapsed one recovered), groups
129 and cubes 124 all now uniquely named.

**The SEC transformation registry was shipped but never loaded.**
`resources/sec-transform-types.json` was present and unreachable: `ixt-sec` was
not in `builtInPrefixTaxonomies`, and the synthesised report-entry module neither
imported it nor declared its prefix. All three are fixed.

Together these took the Microsoft filing's log from **~150 messages including one
of 50 KB** to **139**, with the remaining classes all understood:

| count | code | what it is |
|---|---|---|
| 56 | `oimte:factValueDataTypeMismatch` | the untransformed-value case of §3.3: an `ixt-sec` transform is *resolved* but not *applied*, so "☒" fails `xs:boolean` |
| 47 | `oimte:invalidQNameReference` | the shipped SEC registry declares only `boolballotbox` and `exchnameen`; this filing also uses `duryear` (27), `durwordsen` (10), `numwordsen` (5), `durday` (2), `stateprovnameen` (2), `durmonth` (1) |
| 21 | `oimtc:inconsistentCalculationUsingRounding` | real calculation findings |
| 10 | `oimte:invalidDomainNetworkObject` / `invalidDomainTarget` | `ecd:` compensation members declared as concepts, not members |

The 47 are a **spec-data** gap, not a code one — the six missing transforms
belong in `spec-taxonomies/sec-transform-types.json` upstream. The 56 are the
open item already recorded in §3.3.

**Not reproduced, and probably not ours:** an `IOerror` resolving
`http://www.xbrl.org/lrr/arcrole/esma-arcrole-2018-11-21.xsd` (genuinely
referenced at `msft-20250630.xsd:693`) to a path inside an unrelated
`ifei_2027-01-01_taxonomia_v1.0` taxonomy package, then looking it up as a member
of the Microsoft zip. That needs that package enabled, which no run here had. The
plugin passes URLs and never constructs archive members, so this looks like the
PackageManager remapping / FileSource interaction in core Arelle. Loading the
same filing with the XbrlModel plugin disabled distinguishes the two.

### 3.7 ESEF anchoring was being silently discarded

Chasing the ESMA arcrole in §3.6 found a real conversion loss, not a packaging
problem. `http://www.xbrl.org/lrr/arcrole/esma-arcrole-2018-11-21.xsd` is an
ordinary schema in the XBRL.org **link role registry**, fetched over the web as
part of the DTS; nothing remaps it. The Microsoft filing declares an
`arcroleRef` to it (`msft-20250630.xsd:693`) but uses **no** anchoring arcs, so
nothing was lost there. L'Oreal's 2025 ESEF package does use it — and every one
of its anchoring relationships was dropped.

`legacyTaxonomyToOimModule` translated exactly two arcroles: presentation
(`parent-child`) and calculation (`summation-item`), plus the XDT arcroles that
cube inference consumes. Anything else — an LRR arcrole, a filer-defined one —
had no relationshipType object and no network, so it simply was not in the
compiled model. For ESEF that is a regulatory construct going missing: the RTS
requires every extension concept to be anchored to a base-taxonomy concept.

`_customArcroleNetworks` now translates any arcrole nothing else handles:

* a `relationshipType` object per arcrole, taking its **canonical name** where a
  built-in model declares one. `core.json` already declares the LRR deprecation
  arcroles as `xbrl:dep-*`, so those resolve to the same objects every other
  model uses. The known-name map is read from the shipped resources rather than
  restated, so adding one to a spec taxonomy is picked up here for free.
* the arcrole's `<definition>` as an `xbrl:documentation` label — a
  relationshipType object has no documentation property.
* a network per (arcrole, linkrole), with roots declared from `xbrl:rootSource`
  as the presentation networks are.

Measured on L'Oreal: `loreal:group_Anchoring_wider_narrowerNet`, **59
relationships**, plus 9 relationshipTypes the DTS declares and uses that were
previously absent. Error profile unchanged (34 pre-existing calculation
duplicate-fact findings); Microsoft unchanged; conformance 725/756 unchanged.

**Open, and a spec decision rather than a code one.** The synthesised name is
`ns6:wider_narrower` — stable for a given arcrole URI, but with a minted prefix,
because nothing registers one. Making it canonical is exactly what §"lrr entries
should be a spec taxonomy" asks for, and the precedent is already in `core.json`
with `xbrl:dep-*`. Whoever owns the spec taxonomies should decide where ESMA's
wider-narrower (and the rest of the LRR) lives and under which prefix; the loader
will then use that name automatically and stop minting one.

### 3.8 Custom transform registries reached the model but not the value

Yes — SEC's `ixt-sec:*` transforms map to functions the same way the standard
registries do. Core keeps the standard tables in `FunctionIxt.ixtNamespaceFunctions`
and anything else in `modelManager.customTransforms`, filled from the
`ModelManager.LoadCustomTransforms` hook; the EDGAR transform plugin registers 18
`ixt-sec` functions through it. Core's own inline evaluator tries the standard
table and **falls back to `customTransforms`** (`ModelInstanceObject`).

`FactValueResolver.applyTransformation` did not have that fallback. It looked only
in `ixtNamespaceFunctions` and, on a miss, returned the text unchanged — so a
value re-derived from the document kept its untransformed form ("☒" where
`xs:boolean` is expected), which then failed its datatype for a reason pointing at
the value rather than at the missing transform. That is the 56
`factValueDataTypeMismatch` of §3.6, and the same root as the
`us-gaap:CommercialPaper` = `"no"` case in §3.3.

The resolver now falls back to `modelManager.customTransforms`. Measured on the
Microsoft filing:

| plugins | `factValueDataTypeMismatch` |
|---|---|
| `XbrlModel` | 56 |
| `XbrlModel` + `EDGAR/transform` | **0** |

### The registry the model declares, completed

`sec-transform-types.json` declared **2 of the 15** transforms SEC formally
registers — `boolballotbox` and `exchnameen` — which was the remaining 47
`invalidQNameReference`. SEC publishes the rest formally, in the EDGAR plugin:

| source | supplies |
|---|---|
| `EDGAR/transform/transformationRegistry/schema/inlinexbrl-sec-transformation.xsd` | the input dataTypes, with their patterns / enumerations |
| `EDGAR/transform/transformationRegistry/registry/ixt-sec-*.xml` | each transform's signature (input and output type) and its documentation |

The module is now generated from those rather than hand-written, so re-running the
generator tracks the registry. The thirteen added are `countrynameen`,
`datequarterend`, `durday`, `durhour`, `durmonth`, `durweek`, `durwordsen`,
`duryear`, `edgarprovcountryen`, `entityfilercategoryen`, `numwordsen`,
`stateprovnameen`, `yesnoballotbox`. Written to both copies — the plugin's
`resources/` snapshot and `oim/specifications/oim-taxonomy/spec-taxonomies/`
(branch `spec-dev-1`, uncommitted).

Purely additive: the two existing entries are left exactly as curated. Worth a
look before committing — the registry gives `exchnameen` an output of `xs:token`
where the curated entry refines it to `dei:edgarExchangeCodeItemType`. The curated
value is kept; the registry is not the more precise of the two.

Not added: `numinf`, `numnan` and `numneginf`. The EDGAR plugin implements them
and the schema declares their input types, but they have **no registry entry**, so
there is no formally stated output type to record and none was invented.

Net effect on the Microsoft filing, from ~150 messages including one of 50,000
characters:

| plugins | messages |
|---|---|
| `XbrlModel` | 95 — the 56 datatype mismatches remain, needing the transform *functions* |
| `XbrlModel` + `EDGAR/transform` | **38**, of which 31 are genuine findings (21 calculation inconsistencies, 10 `ecd:` compensation members declared as concepts rather than members) and 7 informational |

`arelle:calcNotCheckedNonNumericValue` also disappears: `us-gaap:CommercialPaper`
= `"no"` now transforms through `numwordsen` to 0, so §3.3's uncheckable
calculation becomes checkable. That is the §3.3 open item closing for the SEC
case — though the general one remains: **a report whose transform genuinely
cannot be applied still keeps its raw text as though it were the value.**

### 3.9 Domain members that are not abstract

The last finding class on the Microsoft filing was ours, not the filing's. Ten
`oimte:invalidDomainNetworkObject` / `invalidDomainTarget` on `ecd:` members —
SEC's pay-versus-performance taxonomy, so this affected every US filing carrying
that disclosure since 2023.

`_classify` called a concept a member when `isDomainMember and isAbstract`. But
Arelle's `isDomainMember` is an **alias for `isPrimaryItem`** — true of every
ordinary line item — so abstractness was carrying the entire distinction. ECD
declares its members non-abstract:

```
ecd:AggtPnsnAdjsSvcCstMember   type dtr-types:domainItemType   abstract=false
```

so each was emitted as a *concept*, and the domain network that targeted it then
failed its `allowedDomainItem`. A concept whose **type** is `domainItemType` is
now classified as a member whether or not it is abstract; the abstract-primary-item
test stays for domain roots declared with other types.

Microsoft: concepts 12,488 → 12,484, members unchanged at 5,581 — those four were
being emitted as both. All ten findings gone. L'Oreal unchanged, conformance
725/756 unchanged.

With this, the filing loads with **only genuine findings**: 21 calculation
inconsistencies, and nothing else.

### 3.10 A saved compiled model does not round-trip

Found while measuring the pruning change, and much the larger defect. Reloading
a saved compiled model that retains `factSources` **re-derives its DTS from the
source document and loses its facts**:

| | facts | concepts | networks | cubes |
|---|---|---|---|---|
| `msft-prune.json` as saved | 1,829 | 515 | 0 | 0 |
| the same file, reloaded and re-saved | **0** | 12,484 | 141 | 124 |

The log shows why: validating the reloaded model logs `Load OIM Taxonomy file
0000950170-…-xbrl.zip` and `Loaded 1829 facts from inline report`. The saved
model already carries those facts, but `materializeFactSourceFacts` does not
notice, re-runs the whole legacy compile, and the freshly built module then
displaces the saved one — the pruned taxonomy is replaced by the full one and
the facts go with it.

Two consequences worth separating:

* **The artifact is not reloadable.** Everything the save modes achieve — the
  fact closure, the viewer-tailored Form B, derived content — is undone by
  reading the file back. This is pre-existing, on every save mode.
* **Reload error counts are not a quality measure.** The inflated figures on a
  reloaded model (3,654 `factValueLocatorRequiredForValueSources`, twice 1,827;
  3,280 `oime:invalidJSONStructure`) are artefacts of this, not of the artifact.
  A comparison of prune output "before and after" a change, measured by
  reloading, measures the broken path rather than the change.

**Fixed.** A factSource whose module already carries facts has nothing to
materialize: the facts are the ones being described, not ones to produce. One
test in `materializeFactSourceFacts` covers it, and the factset case is
unaffected — a factset carries factSources and no literal facts, and one from
`saveOIMFacts` names a *custom* fact map that never reached this function at all
(only built-in maps are materialized here). A saved model's factSource names the
**built-in** map, which is why it re-ran.

Round trip now exact — 1,829 facts / 515 concepts / 0 networks / 0 cubes in and
out — and validating a reloaded model went from 4.00 s to 0.68 s, since it no
longer recompiles the DTS.

### 3.12 Two serialization defects the round trip exposed

With the re-derivation gone, the reload of a saved model still reported 3,280
`oime:invalidJSONStructure`. Two systematic faults, the same shape as the
unit-tuple and `_periodValue` leaks of §3.4 — an internal representation reaching
the serialization:

* **`decimals` was emitted as a string.** `LoadInlineFacts` took Arelle's raw
  `@decimals` attribute, so every numeric fact serialized `"decimals": "-6"`
  where the model requires a number (or the string `"INF"`). 1,443 messages.
* **A prefixless QName serialized as a bare local name.** `xbrl:entity` is built
  as *scheme:identifier*, and a document that declares no prefix for the scheme
  URI — SEC filings declare none for `http://www.sec.gov/CIK` — left the QName
  unprefixed, so it emitted `"0000789019"`, which is not a QName. 1,829 messages,
  one per fact. `SaveModel` now mints and declares a prefix for a namespace that
  arrived without one (`cik` for the SEC scheme, `ns0`… otherwise), so the
  emitted value is a QName resolving to the same expanded name.

Reload of a pruned Microsoft model, `oime:invalidJSONStructure`: **3,280 → 2**.

Left, both pre-existing and separate:

* the 2 remaining were nil facts — **since fixed, and it was ours** (§3.13);
* `oimce:invalidURIForReservedAlias` for `xbrli`, because the legacy DTS binds
  that prefix to the 2003 instance namespace and the reserved alias is the 2026
  one;
* `oimte:noFactSpaceForFact` per fact on a **prune**-mode reload is inherent to
  that mode rather than a defect: prune drops the cubes, so no fact matches one.

### 3.11 Pruning kept every type definition

`PruneModel` treated the type-definition collections — property, label,
reference, relationship, cube, collection and model types — as always-keep, on
the stated grounds that they are small. True of a 12,000-concept filing, and
badly false of a small one: a two-fact conformance model emitted 67 property
types to use 2, and unreferenced type definitions were **44% of the file**.

Worse, keeping them wholesale while pruning what *they* referenced produced 72
dangling `oimte:invalidQNameReference` in the emitted artifact — the retained
type definitions pointed at datatypes and domains the closure had dropped.

`pruneClosure` now follows the references that reach type definitions (an
object's `properties`, a label's `labelType`, a reference's `referenceType` and
its own properties, a network's `relationshipTypeName` and relationship
properties, a cube's `cubeType`, a propertyType's `dataType`), and `pruneSkip`
filters those collections by closure membership:

| | before | after |
|---|---|---|
| conformance model, prune | 57.1 KB, 72 dangling refs | **16.3 KB, 0** |
| conformance model, report | 63.5 KB | 33.2 KB |
| Microsoft filing, prune | 3.13 MB, 67 property types | 3.09 MB, 2 |
| Microsoft filing, report | 8.71 MB, 18 dangling refs | 8.67 MB, **0** |

The large-filing saving is ~1%, as the original comment implied; the small-model
saving is 71%, which is what makes compiled-model conformance cases practical.

**Still oversized, and the cause is known.** `report` mode retains 12,484 of
12,488 concepts. `_allFactsCube` builds its concept domain as *every concept of
the taxonomy* (appendix B.1: so §5.6 is satisfied for any calculation), and
`pruneClosure` retains a cube by its concept domain, so the whole taxonomy comes
back. Measured on the Microsoft filing, the domain needs 515 entries, not
12,484 — a 95.9% reduction:

| | |
|---|---|
| concepts with a reported fact | 515 |
| concepts named in the cube's calculation networks | 220 |
| union — what §5.6 requires | **515** |

The rule must be the **union**, not the reported set: §5.6 requires every concept
of an associated calculation to be in the domain whether or not it was reported.
Here every calculation concept happens to have a fact, so the two coincide; a
filing whose calculation names a concept it did not report this period would
fail if the domain were pruned to reported facts alone.

**Implemented** (`_allFactsCubeConcepts`). A `.xsd` taxonomy entry point has no
facts to compute the union from, and there every concept is admitted exactly as
before, so the cube stays usable and §5.6 holds for any calculation.

| | before | after |
|---|---|---|
| all-facts concept domain | 12,484 | **515** |
| Microsoft, full | 9.60 MB | **7.46 MB** |
| Microsoft, report | 8.67 MB, 12,484 concepts | **4.24 MB, 580 concepts** |
| Microsoft, prune | 3.09 MB | 3.09 MB (prune drops cubes) |
| `.xsd` entry point | domain 12,484 | domain 12,484, unchanged |

Report mode is what this was for: it now emits the fact closure plus the
presentation structure — 580 concepts — instead of the entire taxonomy.

Verified rather than assumed: Microsoft and L'Oreal both produce **identical**
error profiles to before (21 calculation inconsistencies, 34 duplicate-fact
findings), with no `oimtc:summationItemConceptNotInCube` and no
`oimte:noFactSpaceForFact` — so the restricted domain admits every fact and
satisfies §5.6. Conformance 725/756 unchanged; the staged viewer still binds
2,146 overlays from a model 22% smaller.

### 3.13 Nil facts: the specification was right and we were not

The two schema errors left over from §3.12 were nil facts, and the question of
whose defect it was is answered by the conformance suite. Every nil fact in it
takes the same form:

```json
{ "name": "…", "factDimensions": { … },
  "properties": [ { "property": "xbrl:nil", "value": "xbrl:unknownNilReason" } ] }
```

with **no `factValues` at all** — four tests, all consistent
(`FACT-RequiredDisclosureNoValue`, `…NoValueOpenEnum`,
`NIL-DuplicateFactWithNilAndValue`, `…WithNilAndValueSource`). Nil is a property
of the *fact*, naming a nil reason member; the fact reports nothing, so it has
nothing to report a value for.

So the specification is right, and the schema is right to require `value` or
`valueSources` of each fact value — a nil fact simply contributes none.
`LoadInlineFacts` was building a fact value unconditionally and attaching it
whether or not the fact was nil, emitting `{"name": "…_fv"}` with neither. Fixed:
a nil fact is given no fact values.

With that, a saved compiled model of the Microsoft filing validates against the
derived-content document schema with **zero errors**, where it began this work
with 3,280.

### 3.14 The same filing produced a different model each run

Found by asking the right question rather than by a failing test: could an
intermediate `set` need to be ordered for run-to-run determinism?

It could. Two loops emitted a presentation network's root relationships by
iterating a `set`:

```python
rels = [{"source": "xbrl:rootSource", "target": n} for n in srcs if n not in tgts]
```

A set of strings iterates in hash-randomised order — Python randomises string
hashing per process by default — so **39 of 145 networks came out with their
root relationships in a different order on every run**. Same relationships, same
count, different document. Both are now `sorted(srcs - tgts)`.

Measured before and after, on three runs of the same filing:

| | before | after |
|---|---|---|
| `xbrlModel` byte-identical across runs | **no** | **yes** |
| `derivedContent` identical (bar its timestamp) | yes | yes |

Derived content was already stable, which is why nothing had noticed: the facts,
cubes, results and cube contents are all built from ordered structures. It was
the translated taxonomy that moved.

This is worth more than tidiness. `sourceModelChecksum` in the derived-content
specification binds derived content to *a specific serialised model* so a
consumer can tell whether it is stale — and a model that serialises differently
each run cannot be checksummed at all. The feature was unimplementable until
this was fixed, and nothing said so.

It also makes a saved model diffable: two runs, or a run before and after a
change, now differ only where something actually changed.

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

## 5. When validation happens is a workflow decision

The workflow has to offer this as a **step option**, because the answer differs
between a desktop user and a production receipt pipeline, and the artifact each
produces differs with it.

The question is where calculation (and other) validation results come from when
a report is viewed. Two answers:

| | validate at receipt, carry the verdict | validate at viewing |
|---|---|---|
| who | production intake — EDGAR does this | a desktop user loading a filing to look at it |
| artifact | model carries per-binding results and their provenance | model carries none; the viewer computes |
| stable over time | **yes** | no |
| needs | `SaveModel` to emit results (not built) | a validating viewer (partially built) |

**The temporal argument is the deciding one.** Validation on receipt is a
statement about a moment: this is what the rules concluded, then. Revalidating at
viewing time answers a different question, because standards, rules and
implementations move between receipt and reading — so the same artifact would
report differently over the years, with nothing recording which reading was
authoritative or when it changed. For a disseminated artifact that is a
misrepresentation of what was filed and accepted, not a fresher opinion.

This was decided for calculations on 2026-08-29 in favour of carrying the
verdict; see `HANDOVER-calculations.md` §2.4 in the viewer repository, which also
lists the viewer-side consequences. The workflow consequences are here:

1. **An emit step.** `SaveModel` needs to write per-binding results — which
   binding, consistent or not, the `oimtc:` code where not. It writes none today.
2. **Provenance alongside them.** When, by what processor version, against which
   rule set. A carried verdict without that is no more interpretable than a
   recomputed one; being able to say *this is what validation concluded, then* is
   the entire point.
3. **Both profiles remain legitimate.** A desktop user opening a filing they just
   downloaded has no receipt event and no carried verdict, and validating locally
   is the right thing for them. So the step is an option in the workflow, not a
   mode the product is in.
4. **The three states must stay distinguishable** end to end: validated and
   consistent, validated and inconsistent, and *not validated*. A model carrying
   no results must not be presented as though it carried a clean bill — which is
   the failure mode a silent local recompute would produce, since it would look
   identical to a carried verdict.

Point 4 is the one to design for rather than bolt on: it is the same
silent-wrong-answer shape as the locator failures elsewhere in this work, where
a plausible result and a correct one are indistinguishable to the reader.

## 6. Artifacts to work against

`/Users/hermf/temp/pdf/Microsoft/` — full characterisation in its `FINDINGS.md`.

| file | |
|---|---|
| `0000950170-25-100235-xbrl.zip` | the EDGAR filing: instance + 2 MB extension schema |
| `msft-20250630.xsd`, `msft-20250630.htm` | extracted from it, needed for relative resolution |
| `msft-facts.json` | §2.1 output, 1,708 facts |
| `msft-dts-model.json` | §2.2 output, 123 cubes |
| `msft-facts-pdf.json` | after `alignFactsToSurface`, 1,525 of 1,800 located |
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

## 7. Suggested order

The desktop workflow (§8.2) is now built, and with it artifact portability.
What remains:

1. **The validation-result emit step** (§5), which the calculations work is
   waiting on: `SaveModel` writes no per-binding results, and a model that
   carries none must not read as a clean bill.
2. **The journal applier** (§4), which closes the loop. Independent of
   everything else; the journal format is settled and has a working producer.
3. **A PDF surface for the staged viewer.** The staging handles HTML documents.
   The viewer's PDF surface additionally needs pdf.js `cmaps` and
   `standard_fonts`, which the demo directory symlinks out of `node_modules`
   rather than taking from the build — so they are not in `viewer/dist` for
   `stageViewerBundle` to copy.
4. **Multi-document IXDS source mappings.** `LoadInlineFacts` records one
   sourceMapping per report (its own TODO), so a multi-document report binds
   every fact to the first document. The staging copies all documents of the
   set, which is what a per-document mapping would need, but nothing
   distinguishes them yet.

5. **A reserved cube type for the legacy accommodation cube**, if the working
   group wants one. The cube is now marked by a *model-defined* type —
   `<prefix>:legacyAccommodationCubeType`, deriving from `xbrl:reportCube` — so a
   consumer can tell a mechanism from a reporting structure by its local name
   instead of inferring it from absence in the group tree. A reserved type would
   make that a QName match across models rather than a naming convention; this
   does not block on it, and such a type would simply become the model-defined
   one's `baseCubeType`.

   Recorded because the naming is the substance: the cube is *not* named for what
   it contains. "allFactsCube" read as a feature to adopt, when nothing should
   produce one but this translation, and it invited confusion with ESEF's
   `[999999] Line items not dimensionally qualified` — which is the opposite kind
   of object, authored by the filer to satisfy the RTS and belonging in a
   navigator.

Also noted while working, unowned: the untransformable-inline-value case in §3.3.

## 8. The workflow paths

What each category of use needs. §8.1–§8.4 are the paths through the *tooling*;
§8.5 is the distinction that cuts across them, which emerged late and is the one
to hold on to.

### 8.1 Arelle without the plugin

Unchanged, and must stay so. Nothing in this work touches a load that does not
activate `XbrlModel`.

### 8.2 Desktop, with the plugin

The traditional Arelle sequence, all four steps now present:

| step | state |
|---|---|
| load a legacy or XBRL Model entry point | works — `.xsd`, inline `.htm`, `.xml`, xBRL-JSON/CSV, OIM `.json`/`.cbor`, EDGAR ZIP |
| validate after loading | works — on by default, Tools ▸ "Validate XBRL model on load" defers it |
| display the Tk views | works — Concepts, Groups, Networks, Cubes, Facts, ... |
| invoke the ixbrl-viewer when there is something to view | **`ViewerLaunch.py`** |

`iXBRLViewerPlugin`'s own GUI launch (`guiRun`) builds a viewer *document* from a
legacy inline `ModelXbrl` and does nothing for anything that is not
`Type.INLINEXBRL`. A compiled model is not that, and does not need it: the
XbrlModel overlay takes a *plain* document plus an OIM model, as
`?xbrlModel=<model>` on the viewer URL (§1). So the work is staging, and
`ViewerLaunch.stageForViewer` does it — the model, the document(s) it locates
facts in, and the viewer bundle, in one directory.

Three things it has to get right:

- **Where the directory goes** follows Arelle's existing convention, the one
  `EDGAR/render` uses (`setProcessingFolder` plus its reportsFolder resolution):
  a subdirectory of the directory holding the entry file, or — when the entry
  file is inside a zip, report package or taxonomy package — a *sibling* of the
  archive, because `FileSource.basefile` is the archive's own path. A read-only
  location falls back to the web cache directory for that URL, then to a temp
  directory. Named `out`, as EDGAR's GUI viewer output is; settable through the
  `xbrlModelViewerFolder` config key.
- **The model must be portable.** `documentInfo.sourceMappings` is rewritten to
  name the staged copy (`saveFiles(..., sourceUrlRewrite=...)`), so the viewer
  resolves the document from the model and the directory is self-contained. As
  loaded it holds an absolute local path, or the path of the archive.
- **The whole bundle travels.** The viewer build is code-split; copying only
  `ixbrlviewer.js` gives a viewer that loads and then fails to open a document,
  with the cause visible only in the browser console.

Triggered on load when the model has something to show a reader against — a
sourceMapping naming a document *and* facts located in it (`hasViewableSource`).
Tools ▸ "Open iXBRL Viewer on load" turns that off; Tools ▸ "View XBRL model in
iXBRL Viewer" opens it on request.

Measured, on the EDGAR filing ZIP: **2,146 bound fact overlays** over the inline
document, from a single 8.9 MB compiled model with no separate taxonomy.

The viewer bundle is located from the loaded `iXBRLViewerPlugin`, from the plugin
configuration's `moduleURL` (so a viewer plugin that failed to load still
provides its bundle), or from the `xbrlModelViewerBundleDir` config key.

**Known interaction:** with both plugins active, `iXBRLViewerPlugin.guiRun` also
fires on `CntlrWinMain.Xbrl.Loaded`. Its `processModel` is guarded by
`isInlineDoc` and does nothing for a compiled model, but `generateViewer` is
still called with an empty builder. Noise, not breakage; unverified in the GUI.

### 8.3 Command line and API

Complete for loading and saving; incomplete for what the saved artifact carries.

```bash
# filing (or ZIP, or .xsd, or factset) -> one self-contained compiled model
arelleCmdLine --plugins XbrlModel -f <entry point> --saveOIMmodel model.json \
    [--oimSaveMode full|prune|report]

# ... or a servable directory: model + document(s) + viewer bundle
arelleCmdLine --plugins "XbrlModel|<path>/iXBRLViewerPlugin" -f <entry point> \
    --saveXbrlModelViewer out/
```

Validation runs first for either, whether or not `--validate` was given (§3.2).
`--saveXbrlModelViewer` is the command-line half of §8.2 — the same staging, into
a named directory, with no browser opened. Still missing: the verdicts
themselves (§5).

### 8.4 Tagging feedback from the viewer

**Built** — `ApplyTaggingJournal.py`, `--applyTaggingJournal <file>`.

The shape was not obvious and is worth recording, because it is not a
processing option: **two parties run this step and they want different
things**, and which one is running decides what the artifact claims.

* A **preparer**, tagging a report they are authoring. The bindings are their
  own content — the filing says where its values come from — so the journal is
  applied *into the model*, and the result is a filing with no derived content
  at all. `--taggingJournalInto model`.
* A **disseminator**, tagging a report somebody else filed: re-rendering a
  prior filing onto a surface it was never tagged against (an N-CSR unwieldy
  as XHTML, laid out as PDF), or locating values for a viewer. Those bindings
  are not the filer's content, so they become *derived* fact values with a
  `basis` of `bound`, beside a model left exactly as filed.
  `--taggingJournalInto derivedContent` (the default).

The preparer has a second choice the model already distinguishes, selected by
`--taggingValueAuthority`: whether the **document** text is the point of truth
(the fact carries value sources and no value) or the **value** is (the fact
carries the value it was given — from an accounting system, a prior filing, a
spreadsheet — and the binding is an anchor that merely locates it). Both are
faithful; they differ in what the filing asserts.

Measured on the Microsoft filing with a four-entry journal:

| | the fact in the model | derived content |
|---|---|---|
| `into derivedContent` | untouched, `xbrl:htmlElementId` as filed | 3 `bound` fact values with the tagger's sources |
| `into model` (document) | `valueSources` + `scale` from the journal | no `bound` entries |
| `into model` (value) | `value` + `valueAnchors` + `scale` | no `bound` entries |

All three validate against the derived-content document schema with zero
errors.

**A journal entry names its fact by the viewer's fact id**, which for a located
fact is `<reportIndex>-<htmlElementId>` and resolves against the model. For a
fact the viewer could not locate, or placed on a PDF, the id is a synthetic
`hf-N` / `pf-N` — a position in the order the adapter happened to build, not an
identity — and such an entry is reported unapplied rather than guessed at. That
is a real limit on the PDF re-rendering case above and wants a stable id from
the producer side before it is usable there.

### 8.5 Who is running the tool decides what the artifact claims

The paths above describe what the tooling does. This is about who is asking, and
it turned out to matter more than any of them, because the same operation
produces artifacts that assert different things.

**A preparer** uses the tooling while authoring a filing: importing accounting
data (a prior year's filing, this year's tables or spreadsheets), letting the
tooling attempt the mapping to value sources in the report, tagging what it could
not place, and choosing whether the document's text or the imported value is the
point of truth. Everything they produce is **their own content**. The artifact is
a filing, and it should carry **no derived content at all** — nothing in it was
computed by a processor about somebody else's report.

**A later party** — an authority disseminating, a tool preparing a viewer, anyone
re-rendering a prior filing onto a surface it was never tagged against (the SEC
N-CSRs, unreadable as XHTML, laid out as PDF) — produces **only derived content**.
The model is left exactly as filed; the resolved values, the fact-to-cube
association, the calculation verdicts and any hand-made bindings sit beside it,
attributable and separable.

Both parties run the same commands. What differs is which artifact is honest, and
the tooling makes them state it rather than inferring:

| | preparer | later party |
|---|---|---|
| tagging journal | `--taggingJournalInto model` | `--taggingJournalInto derivedContent` (default) |
| fact aligner | `--alignInto model` | `--alignInto derivedContent` (default) |
| what the fact carries | the binding, as the filing's own | unchanged, as filed |
| derived content in the output | none | all of it |

`--alignInto` was added 2026-08-30 for the HTML5 surface
(`tools/alignFactsToSurface.py`, `--align-to-html5`), which is why the aligner and
the journal applier no longer produce different shapes for the same kind of
finding. The PDF surface takes `model` only; see §10 of
`tools/HANDOVER-html5-aligner.md` for why and what would close it.

For the aligner's half of the axis this is no longer only a local convention: the
OIM Taxonomy Derived Content specification now carries it, in the derived fact
value object section — an author tagging a further rendering they publish
themselves extends their model, anyone else records derived content, and since
neither is visible in the serialisation the producer states which. The tagging
journal's half remains as described above; the spec deliberately leaves open when
a tagging decision is *accepted* into a model.

The reason to keep the distinction visible is that the failure it prevents is
silent: a derived value emitted onto a fact is indistinguishable from a reported
one, and a filing that carries a processor's conclusions reads as though the
filer asserted them. §3.4 and the derived-content work are both consequences of
taking it seriously.
