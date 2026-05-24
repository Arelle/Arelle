# XbrlModel/Formula — XBRL Query and Rules Language Plugin

An Arelle plugin that evaluates rules and queries written in the
**XBRL Query and Rules Language** (Xule) against OIM-based XBRL filings
loaded through the [XbrlModel](../) plugin.

The language is specified in
[`oim/specifications/oim-taxonomy/Formula/formula.md`](https://gitlab.xbrl.org/oim/oim/-/blob/spec-dev-1/specifications/oim-taxonomy/Formula/formula.md)
and is a successor to XBRL Formula 1.0 with broader querying capabilities
targeting the Xbrl Model 1.0 data model rather than XBRL 2.1 XML.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Rule File Syntax (`.xule`)](#rule-file-syntax-xule)
3. [CLI Options](#cli-options)
4. [Plugin Hooks](#plugin-hooks)
5. [Architecture and Modules](#architecture-and-modules)
6. [Fact Alignment — Design and Performance](#fact-alignment--design-and-performance)
7. [VectorSearch Integration](#vectorsearch-integration)
8. [Extending the Language](#extending-the-language)
9. [Testing](#testing)
10. [Dependencies](#dependencies)
11. [Known Limitations and Future Work](#known-limitations-and-future-work)

---

## Quick Start

### Command line

```sh
python arelleCmdLine.py \
    --plugins XbrlModel/Formula \
    --formula-ruleset path/to/rules.xule \
    path/to/filing.json
```

Multiple rule sets (files or directories) may be provided:

```sh
python arelleCmdLine.py \
    --plugins XbrlModel/Formula \
    --formula-ruleset rules/core/ \
    --formula-ruleset rules/extensions/extra.xule \
    --formula-output-file results.json \
    filing.json
```

### Arelle GUI

1. Open **Tools → Manage Plug-ins** and enable **XbrlModel/Formula**.
2. Open an OIM filing (JSON, CSV, or XML via XbrlModel).
3. Provide the ruleset path through the Arelle formula options dialog or
   the `--formula-ruleset` command-line switch.

### Python API

```python
from arelle.plugin.XbrlModel.Formula.FormulaRuleSet import loadRuleSet
from arelle.plugin.XbrlModel.Formula.FormulaContext import FormulaGlobalContext
from arelle.plugin.XbrlModel.Formula.FormulaInterpreter import evaluateRuleSet

ruleSet = loadRuleSet(["path/to/rules.xule"], cntlr=cntlr)
ctx = FormulaGlobalContext(ruleSet, txmyMdl, cntlr=cntlr)
evaluateRuleSet(ctx)

for result in ctx.results:
    print(result["ruleName"], result["message"])
```

---

## Rule File Syntax (`.xule`)

Xule source files use the `.xule` extension.  A file contains any
combination of **namespace declarations**, **constants**, **output rules**,
and **assert rules**.

### Namespace declarations

All three syntactic forms are accepted (per `formula.md`):

```xule
namespace gaap <https://xbrl.fasb.org/us-gaap/2024>
namespace ifrs = "https://xbrl.ifrs.org/taxonomy/2023"
namespace "http://default.example.com/ns"          // default namespace
```

Namespaces declared here are merged with any namespaces already known to
the loaded taxonomy.

`namespace-group NAME = expr` declarations are parsed and silently absorbed
(xule extension, no semantics in this interpreter).

### `output-attribute` declarations

```xule
output-attribute file-content
output-attribute file-location
```

Declared output attributes are accepted at the top of a ruleset and recorded
on the rule set object (no semantic effect today; reserved for future CSV /
JSON output assignment).

### Constants

```xule
constant $threshold = 0.01
constant $assetConcepts = set(gaap:Assets, gaap:AssetsCurrent)
```

Constants are evaluated once and cached for the lifetime of the rule run.
They may be expressions of arbitrary complexity, including function calls
and fact queries.

### Output rules

An `output` rule emits a result for every aligned combination of its fact
queries.

```xule
output EquitiesValue
    @gaap:Assets + @gaap:Liabilities
message "Assets {$rule-value} for period {$rule-value.period}"
```

### Assert rules

An `assert` rule fires (produces an error/warning result) when the
expression evaluates to **false** for an aligned combination.

```xule
assert BalanceCheck
    @gaap:Equity#e == @gaap:Assets#a - @gaap:Liabilities#l
message
    "Equity {$e} does not equal Assets {$a} minus Liabilities {$l}"
```

### Tags

`#tag` binds a fact to a named variable within the rule expression and
message template:

```xule
assert CheckRatio
    @us-gaap:NetIncomeLoss#ni / @us-gaap:Revenues#rev > $threshold
message "Net income ratio {$ni / $rev} is below threshold {$threshold}"
```

### Fact queries (factsets)

Three bracket forms are supported, matching the OIM Formula 1.0 spec:

| Form | Meaning |
|------|---------|
| `{ … }` | Curly factset — match by the listed aspects only; taxonomy-defined dimensions are not constrained. |
| `[ … ]` | Square factset — like curly, but additionally **excludes** facts that carry any taxonomy-defined dimension not listed in the filter set. |
| `@QName` (bare) | Shortcut for `{@concept = QName}`. |

A factset body is a (possibly empty) sequence of **modifiers** followed by
**dimension filters** and an optional `where` clause:

```xule
{ covered nonils                       // modifiers
  @concept = us-gaap:Assets            // dim filters
  @srt:ProductOrServiceAxis = *
  @us-gaap:Revenues as $rev            // filter alias
  where $fact.decimals > -7 }          // post-filter on each fact
```

**Modifiers** (recognised keywords): `covered`, `uncovered`, `nils`,
`nonils`, `nildefault`, `covered-dims`.

**Dimension filter syntax** (per filter):

```
@[@]DimQName[.prop[.prop ...]]  [ (= | != | in | not in) (value | *) ]  [ as $alias ]
```

Examples:

```xule
@us-gaap:Assets                                  // shortcut: @concept = us-gaap:Assets
@srt:ProductOrServiceAxis = *                    // any value present
@concept.balance = 'debit'                       // property chain on a dim
@unit.numerator = unit(iso4217:USD)              // typed core-dim chain
@cube.name = 'StatementOfFinancialPosition'      // pseudo aspect 'cube'
@srt:ProductOrServiceAxis in list(srt:GoldMember, srt:CopperInConcentratesMember)
```

Pseudo aspects recognised: `model`, `cube`, `dimensions`, `language`.
The `model` aspect is a no-op for the single-instance evaluator (any
value accepted).

### Property access

```xule
$fact.period                       // core period aspect
$fact.entity.name.local-name       // chained: entity QName → local-name
$fact.unit.numerator               // simple unit numerator QName
$fact.unit.numerator.local-name
$fact.is-fact                      // BOOLEAN; valid on every value
$fact.id                           // the OIM fact id
$fact.instance                     // the containing instance/model
$fact.cubes                        // SET of cubes the fact participates in
$fact.aspects                      // DICT of core aspect → value
$fact.namespace-map                // DICT of prefix → namespace URI
$concept.data-type
$taxonomy.concepts
$cube.facts
```

Collection projection: `factList.propName` projects the property over each
element of a list or set of facts (e.g. `list({…}).decimals`).

### Built-in functions (selection)

| Category | Functions |
|----------|-----------|
| Aggregates | `sum`, `count`, `min`, `max`, `avg` |
| Existence | `exists`, `not-exists`, `is-nil` |
| Collections | `list`, `set`, `first`, `last`, `index`, `contains`, `sort`, `union`, `intersect`, `difference` |
| Strings | `string`, `concat`, `substring`, `string-length`, `contains-string`, `starts-with`, `ends-with` |
| Math | `abs`, `round`, `floor`, `ceiling`, `power` |
| Taxonomy | `taxonomy([uri])`, `instance([uri])`, `model([uri])` |
| Aspect ctors | `unit(qname [, denom])` |
| Alignment | `alignment()` — returns current dimensional context as a dict |

In the single-instance evaluator, `instance(uri)` and `model(uri)` both
return the currently-loaded XBRL instance/model — the optional URI argument
is accepted but ignored (multi-instance loading is reserved for a future
pass).

### For loops

```xule
for $concept in $taxonomy.concepts
    $concept.name
```

### Set / list literals

```xule
set(1, 2, 3)
list(@gaap:Assets, @gaap:Liabilities)
```

### If / else

```xule
if $x > 0 then $x else -$x
```

---

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--formula-ruleset PATH` | *(required)* | `.xule` file or directory. Repeatable. |
| `--formula-align-threshold FLOAT` | `0.999` | Cosine similarity cutoff for GPU alignment. |
| `--formula-embed-dim INT` | `64` | Embedding dimension for VectorSearch. |
| `--formula-output-file PATH` | *(none)* | Write JSON results to this file. |
| `--formula-default-namespace URI` | *(none)* | Override the rule set's default namespace. Unqualified concept references (`@Assets`) resolve against this URI, taking precedence over any `namespace "URI"` default declared in `.xule` sources. Use this when a test ruleset was written against an older taxonomy version than the filing under test. |

---

## Plugin Hooks

| Arelle hook | Function | Purpose |
|-------------|----------|---------|
| `CntlrCmdLine.Options` | `cmdLineOptionExtender` | Register CLI options |
| `Validate.Finally` | `validateFinished` | Run formulas after validation |
| `TestcaseVariation.Read` | `testcaseVariationRead` | XBRL test suite support |

---

## Architecture and Modules

```
Formula/
├── __init__.py             Plugin entry point, hook registration
├── FormulaValue.py         Value type system
├── FormulaRuleSet.py       Parsed rule data classes + file loading/cache
├── FormulaParser.py        pyparsing grammar → AST
├── FormulaAlignment.py     GPU-accelerated fact alignment
├── FormulaContext.py       Execution context hierarchy
├── FormulaProperties.py    .property accessor dispatch
├── FormulaFunctions.py     Built-in function library
└── FormulaInterpreter.py   AST evaluator and rule runner
```

### `FormulaValue.py`

Defines the value type system used throughout the interpreter.

- `FormulaValueType` enum: `NONE`, `SKIP`, `BOOLEAN`, `INTEGER`, `FLOAT`,
  `DECIMAL`, `STRING`, `QNAME`, `DATE`, `DATETIME`, `DURATION`, `FACT`,
  `FACT_SET`, `CONCEPT`, `CUBE`, `NETWORK`, `TAXONOMY`, `ENTITY`,
  `UNIT_VALUE`, `SET`, `LIST`, `DICT`, `SEVERITY`.
  `ENTITY` and `UNIT_VALUE` wrap the raw fact-dimension value for the
  `xbrl:entity` and `xbrl:unit` core aspects so that `.name`, `.scheme`,
  `.numerator`, `.denominator`, etc. property chains work uniformly.
- `FormulaValue` dataclass: `.type`, `.value`, `.alignment`, `.tagBindings`.
  Constructors: `fromFact()`, `fromScalar()`, `none()`, `skip()`.
- `AlignmentKey = FrozenSet[Tuple[QName, Any]]` — immutable key for a fact's
  non-concept dimensional context.
- `alignmentKeyOf(fact, conceptDimQn)` — builds an `AlignmentKey` by
  collecting all `factDimensions` except the concept dimension.
- Singletons: `NONE_VALUE`, `SKIP_VALUE`, `TRUE_VALUE`, `FALSE_VALUE`.
- Exceptions: `FormulaRuntimeError`, `FormulaAlignmentError`,
  `FormulaIterationStop`, `FormulaSkip`.

### `FormulaRuleSet.py`

Data classes that represent a parsed set of `.xule` rules.

- `NamespaceDecl(prefix, uri)`, `ConstantDecl(name, expr)`,
  `OutputRule(name, expr, messageExpr, severity)`,
  `AssertRule(name, expr, messageExpr, severity)`.
- `FormulaRuleSet`: collects all declarations; `.mergeFrom()` combines
  multiple files; `.allRules` property iterates outputs + asserts.
- `loadRuleSet(paths, cntlr)` — expands directory paths to `.xule` files,
  hashes file contents for a cache key, and returns a merged `FormulaRuleSet`.
  Results are cached in `_ruleSetCache` keyed by the combined hash, so
  unchanged files are not re-parsed between validation runs.

### `FormulaParser.py`

Converts `.xule` text into nested dict/list ASTs using
[pyparsing](https://pyparsing-docs.readthedocs.io/en/latest/) (v3.x).

Key functions:

- `parseFormulaFile(filePath)` — parse a file; runs in a dedicated thread
  with an enlarged stack to support deep pyparsing recursion.
- `parseFormulaString(source, fileName)` — for unit tests.
- `_buildGrammar()` — constructs the full grammar once, thread-safely cached
  by `_getGrammar()`.

The grammar covers: keywords, QNames with optional namespace prefix, all
literal types (integer, float, decimal, string with `{expr}` interpolation,
boolean, none, skip, severity), fact queries (`@QName[filters] #tag`),
function calls, property access (`.prop` and `.prop(args)`), set/list
literals, if/else, for loops, and infix operators via `infix_notation`.

AST nodes are dicts with an `"exprName"` key, e.g.:

```python
{"exprName": "binaryExpr", "op": "+", "left": ..., "right": ...}
{"exprName": "factQuery", "prefix": "gaap", "localName": "Assets",
 "tag": "a", "filters": [...]}
```

### `FormulaAlignment.py`

Implements the fact alignment operation that is the core distinguishing
feature of Xule — see [Fact Alignment](#fact-alignment--design-and-performance)
below.

Key symbols:

- `AlignmentIndex` — dataclass holding `factList`, `factMat` (N×D
  L2-normalised tensor), `device`, `embedDim`, `embedder`.
- `buildAlignmentIndex(txmyMdl, facts, embedDim)` — delegates to
  `VectorSearch.buildAlignmentVectors()`.
- `alignedPairs(indexA, indexB, threshold)` — yields `(factA, factB)` pairs
  with cosine similarity ≥ threshold via a single GPU matmul.
- `alignedGroups(txmyMdl, factSets, threshold, embedDim)` — K-way alignment
  across K slots; builds one index per slot and intersects.
- `exactAlignedGroups(factSets, conceptQn)` — fallback without PyTorch;
  uses `AlignmentKey` dict index and `itertools.product`.

### `FormulaContext.py`

Execution context hierarchy passed through the interpreter.

- `FormulaGlobalContext` — one per rule-run session.
  - `.ruleSet`, `.txmyMdl`, `.cntlr`, `.options`
  - `.namespaces` dict (rule-file declarations merged with taxonomy namespaces)
  - `.constants` dict (evaluated on first access, cached)
  - `.factCache: Dict[QName, List[XbrlFact]]` — per-concept fact lists
  - `.results: List[Dict]` — accumulated rule results
  - `factsForConcept(qn)` — cached lookup
  - `resolveQName(prefix, localName)` → `QName`
  - `vectorSearchReady` property
- `FormulaRuleContext` — one per rule iteration.
  - `.variables: Dict[str, FormulaValue]`
  - `.alignment: Optional[AlignmentKey]`
  - `bindVariable()`, `lookupVariable()` (locals → globals → `$rule-value`)
  - `childContext()` for for-loop scopes

### `FormulaProperties.py`

Provides `.propertyName` access on `FormulaValue` objects.

`getProperty(obj, propName, args, ctx)` dispatches by `obj.type`:

| Object type | Supported properties |
|-------------|---------------------|
| `FACT` | `period`, `entity`, `unit`, `concept`, `dimensions`, `value`, `decimals`, `name`, `is-nil`, `is-fact`, `id`, `instance`, `cubes`, `aspects`, `namespace-map`, `footnotes`, `dimension(qn)` |
| `ENTITY` | `name`, `scheme`, `identifier`, `local-name`, `namespace-uri` |
| `UNIT_VALUE` | `numerator`, `denominator` |
| `CONCEPT` | `name`, `local-name`, `namespace-uri`, `data-type`, `base-type`, `period-type`, `balance`, `is-abstract`, `is-numeric`, `is-monetary`, `nillable`, `substitution`, `labels`, `all-references` |
| `TAXONOMY` | `concepts`, `concept-names`, `cubes`, `dimensions`, `networks`, `namespaces`, `entry-point`, `uri`, `concept(qn)`, `cube(qn, role)` |
| `CUBE` | `cube-concept`, `dimensions`, `facts` |
| `STRING` | `length`, `upper-case`, `lower-case`, `trim` |
| `QNAME` | `local-name`, `namespace-uri` |
| Collections | `count`, `first`, `last` |

### `FormulaFunctions.py`

Built-in function registry `BUILTIN_FUNCTIONS: Dict[str, Callable]`.

`callFunction(name, args, ctx)` looks up the name in built-ins first, then
falls back to user-defined constants that were declared as `function` bodies.

### `FormulaInterpreter.py`

The main AST evaluator.

Top-level entry points:

- `evaluateRuleSet(globalCtx)` — evaluate all constants, then all rules.
- `evaluateExpr(node, ctx)` — dispatch over every AST node type.

Rule execution flow:

1. `_collectFactQueries(ast)` walks the rule expression collecting every
   `factQuery` node into `_FactQuerySlot` objects.
2. For each slot, `factsForConcept()` (or `_findFactsByLocalName()` for
   wildcard queries) retrieves matching facts from the model.
3. `_alignedGroups()` aligns fact lists across slots using the GPU or
   exact-key fallback.
4. `_runRuleIteration()` is called for each aligned K-tuple:
   - Tags are bound as rule-context variables.
   - The rule expression is evaluated.
   - For `AssertRule`: fires if the result is falsy.
   - For `OutputRule`: always emits.
5. Messages are built by `_buildMessage()` using the optional `messageExpr`
   (which may contain `{interpolation}` segments) or a default.

---

## Fact Alignment — Design and Performance

### The problem

A Xule rule such as:

```xule
assert BalanceCheck
    @gaap:Equity == @gaap:Assets - @gaap:Liabilities
```

must match each **Equity** fact with the **Assets** and **Liabilities** facts
that share the same period, entity, and any other dimensional context.

A naïve approach compares all N_equity × N_assets × N_liabilities combinations
— O(N³) comparisons in Python.  For large SEC filings with thousands of facts
this is prohibitively slow.

### The vector approach

1. **Encode** each fact's dimensional context (everything except
   `xbrl:concept`) as a mean-pooled embedding vector using the shared
   `XBRLEmbedder`.  Facts with identical context → nearly identical vectors.

2. **Batch-compare** all N_A × N_B pairs with a single GPU matrix multiply:

   ```
   S[i, j] = cosine_similarity(vecA[i], vecB[j])
   ```

   This is a `(N_A, D) @ (D, N_B)` matmul — a single highly-parallelised
   device kernel on CUDA or Apple Metal (MPS).

3. **Threshold** at `--formula-align-threshold` (default 0.999).  Because
   vectors for identically-dimensioned facts are nearly equal, a high threshold
   cleanly separates aligned from non-aligned pairs with no false positives.

4. **K-way extension**: for K > 2 fact-query slots, the group vector is
   maintained as the running average of the slot vectors and each new slot is
   compared against it.

### Exact fallback (no PyTorch)

When PyTorch is unavailable `exactAlignedGroups()` is used instead:

- `AlignmentKey = FrozenSet[(dimQn, value)]` — a hashable key encoding
  all non-concept dimensions.
- A `Dict[AlignmentKey, List[fact]]` index is built for each slot in O(Σ N_k).
- Groups are formed using `itertools.product` over matching key buckets.

This is exact and correct but does not benefit from GPU acceleration.

---

## VectorSearch Integration

This plugin integrates with `arelle/plugin/XbrlModel/VectorSearch.py`,
which provides the shared embedding infrastructure for the entire XbrlModel
plugin family.

Two functions were added to `VectorSearch.py` specifically to support formula
alignment:

### `buildAlignmentVectors(txmyMdl, facts, embedDim)`

Builds a `(N, embedDim)` L2-normalised tensor — one row per valid fact —
encoding *only* the non-concept dimension tokens.

- Reuses `txmyMdl._xbrlEmbedder` and `txmyMdl._xbrlVectorStore` if already
  built by the XbrlModel plugin or a previous rule run, ensuring a consistent
  shared token space.
- Falls back to `buildXbrlVectors()` if no embedder exists yet.
- Typed dimension values (not QName-valued) are hash-bucketed into the token
  space using `hash(value) % valueTokensOffset`.

### `pairwiseAlignmentScores(matA, matB)`

Returns `matA @ matB.T` — the full `(N_A, N_B)` cosine similarity matrix.
Both matrices must already be L2-normalised (which `buildAlignmentVectors`
guarantees).

### Caching and lifecycle

The embedder and vector store are lazily created on first use and cached as
`txmyMdl._xbrlEmbedder` and `txmyMdl._xbrlVectorStore`.  If the XbrlModel
plugin has already built them (e.g. for semantic search), the formula plugin
reuses them at zero additional cost.  The `--formula-embed-dim` option is
only used when creating a new embedder; if one already exists its dimension
takes precedence.

---

## Extending the Language

### Adding a built-in function

Edit `FormulaFunctions.py` and register a new entry in `BUILTIN_FUNCTIONS`:

```python
def _myFunction(args: List[FormulaValue], ctx) -> FormulaValue:
    # args[0], args[1], ...
    return FormulaValue.fromScalar(result)

BUILTIN_FUNCTIONS["my-function"] = _myFunction
```

### Adding a property

Edit `FormulaProperties.py` and extend the appropriate handler dict or
add a branch in `getProperty()`.

### Adding a new AST node type

1. Add grammar production in `FormulaParser.py` → `_buildGrammar()`.
2. Add a parse-action that produces a dict with a unique `"exprName"` key.
3. Handle that key in `FormulaInterpreter.evaluateExpr()`.

---

## Testing

The reference `.xule` test files live alongside the OIM Formula spec:

```
oim/specifications/oim-taxonomy/Formula/base/
├── factFunctions.xule          // FACT* fact-query tests
├── factFilters.xule
├── collectionFunctions.xule
├── stringFunctions.xule
├── numericalFunctions.xule
├── dateFunctions.xule
├── messages.xule
├── constants.xule              // shared $INSTANCE1, $US-GAAP-2020 …
├── namespace.xule              // shared `namespace …` declarations
├── functions.xule              // shared user-defined functions
└── base-taxonomy-2020.xule
```

The individual fixture files typically depend on shared declarations from
`constants.xule`, `namespace.xule`, and `functions.xule`, so those must be
included in the same ruleset run.

### Running a single fixture from the CLI

```sh
python arelleCmdLine.py \
    --plugin 'XbrlModel|XbrlModel/Formula' \
    --formula-ruleset oim/specifications/oim-taxonomy/Formula/base/namespace.xule \
    --formula-ruleset oim/specifications/oim-taxonomy/Formula/base/constants.xule \
    --formula-ruleset oim/specifications/oim-taxonomy/Formula/base/factFunctions.xule \
    --formula-output-file /tmp/formula-results.out \
    --file oim/specifications/oim-taxonomy/examples/aapl-10K-20250927-factset.json \
    --validate
```

`--formula-ruleset` may be repeated to merge several files into one rule
set.  Results are written both to the Arelle log and (if specified) to the
`--formula-output-file` JSON file.

### Parsing only (no evaluation)

```python
from arelle.plugin.XbrlModel.Formula.FormulaParser import parseFormulaFile
ruleSet = parseFormulaFile("oim/specifications/oim-taxonomy/Formula/base/factFunctions.xule")
print(len(ruleSet.outputRules), "output rules parsed")
```

### Programmatic end-to-end run

```python
from arelle.plugin.XbrlModel.Formula.FormulaRuleSet import loadRuleSet
from arelle.plugin.XbrlModel.Formula.FormulaContext import FormulaGlobalContext
from arelle.plugin.XbrlModel.Formula.FormulaInterpreter import evaluateRuleSet

ruleSet = loadRuleSet([
    "namespace.xule", "constants.xule", "factFunctions.xule",
])
ctx = FormulaGlobalContext(ruleSet, txmyMdl)
evaluateRuleSet(ctx)
for r in ctx.results:
    print(r["ruleName"], r["message"])
```

Clear the rule-set cache between test runs:

```python
from arelle.plugin.XbrlModel.Formula.FormulaRuleSet import clearCache
clearCache()
```

---

## Dependencies

| Package | Required | Purpose |
|---------|----------|---------|
| `pyparsing >= 3.0` | Yes | `.xule` grammar |
| `torch` | Optional | GPU-accelerated fact alignment |
| `arelle.plugin.XbrlModel` | Yes | OIM data model (`XbrlCompiledModel`, `XbrlFact`, …) |

When `torch` is not installed the plugin falls back to exact `AlignmentKey`
matching, which is correct for all cases but slower for large fact sets.

---

## Known Limitations and Future Work

- **Covered/uncovered facts** (`@^Concept`) — the `covered` and `nils`
  flags are parsed and stored in `_FactQuerySlot` but not yet enforced
  during fact lookup; both flags silently have no effect.
- **Typed dimension filters** in `[…]` only support equality (`==`).
  Range comparisons (`<`, `>`, etc.) on typed dimension values are not yet
  implemented.
- **`navigate` expressions** for taxonomy network traversal are parsed
  but the navigation evaluator is not yet implemented; they will raise
  `FormulaRuntimeError` at runtime.
- **External taxonomy loading** via `taxonomy(uri)` currently delegates
  to Arelle's model manager; error handling for unreachable URIs could
  be improved.
- **Parallel rule evaluation** — rules are evaluated sequentially.  A future
  version could run independent rules in parallel using Python's
  `concurrent.futures` if the `txmyMdl` object is thread-safe.
- **Incremental / streaming evaluation** — the current implementation
  loads all facts for a concept at once.  For very large filings a
  streaming model could reduce peak memory.

---

## See Also

- [XBRL Query and Rules Language specification](../../../../../../../../../XBRL.org/oim/specifications/oim-taxonomy/Formula/formula.md)
- [XbrlModel plugin README](../README.md)
- [VectorSearch.py](../VectorSearch.py) — shared GPU embedding infrastructure
- [COPYRIGHT.md](./COPYRIGHT.md) — license information
