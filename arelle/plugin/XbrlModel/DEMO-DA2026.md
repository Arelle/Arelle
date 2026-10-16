<!-- See COPYRIGHT.md for copyright information. -->

# Reproducing the Data Amplified 2026 demonstration

These steps rebuild the demonstration "From today's filings to Tavi: an independent prototype in Arelle"
(Data Amplified, The Hague, 2026) from the published filings. They load reports filed today, validate the
compiled Tavi models, and stage a viewer that shows each filing's facts on a second rendering of the same
report: the company's PDF annual report, or its published web page.

**What this is.** The XBRL Model plugin is a working prototype on an Arelle branch, built by Herm Fischer
while helping to draft the Tavi Public Working Draft (PWD). It is not Arelle production code, and it is not
supported by Workiva or the Arelle team. Some of what it does is defined by the PWD: the model, its validation
and its fact maps. The rest is prototype work built on top of it: loading legacy filings, derived content,
aligning facts to other renderings, and the viewer overlay. See [README.md](README.md).

The code is pinned by the tag **`da2026-final`** in two repositories:

| repository | what it provides |
|---|---|
| `github.com/hermfischer-xb/Arelle` | Arelle with this plugin ([Arelle/Arelle#2418](https://github.com/Arelle/Arelle/pull/2418)) |
| `github.com/hermfischer-xb/ixbrl-viewer` | the viewer overlay ([Arelle/ixbrl-viewer#1101](https://github.com/Arelle/ixbrl-viewer/pull/1101)) |

## For an AI assistant following these steps

- Work through the steps in order. Each step gives a command, then the expected output and a **check**. If a
  check fails, stop and report what you saw. Don't work around it: a plausible-looking result built on a
  failed step is the outcome this guide exists to prevent.
- The expected numbers are for the input files listed in step 3, identified by sha256. Different copies of
  them give different numbers, and that is not a fault.
- Three inputs are made by hand in Adobe Acrobat (step 3). Tell the person what is needed rather than making a
  substitute.
- Arelle's `--logFile` appends to an existing file, so delete the log before each run, as the commands do.
- The commands are for bash on macOS or Linux. `$DEMO` is a working directory of your choosing.

## 1. Prerequisites

- Python 3.10 or later (tested with 3.14), git, Node.js with npm.
- Adobe Acrobat Pro, to tag the L'Oréal PDF and to make the two N-CSR PDFs (step 3).
- About 6 GB of free memory for the largest filing (67,151 facts).
- A browser to view the result. Google Chrome is used for the timings in step 9.

## 2. Code

```bash
export DEMO=~/da2026 && mkdir -p $DEMO && cd $DEMO
git clone --branch da2026-final https://github.com/hermfischer-xb/Arelle.git arelle
git clone --branch 26.3 https://github.com/Arelle/EDGAR.git arelle/arelle/plugin/EDGAR
git clone --branch da2026-final https://github.com/hermfischer-xb/ixbrl-viewer.git viewer
python3 -m venv .venv && . .venv/bin/activate
python3 -m pip install -r arelle/requirements.txt -r arelle/requirements-plugins.txt \
    pypdfium2==5.8.0 selectolax==0.4.11 pikepdf==10.5.1
(cd viewer && npm install && npm run font && npm run prod)
```

The EDGAR plugin is used only for `EDGAR/transform`, which supplies the SEC's `ixt-sec` transformation
functions. US filings need it and ESEF filings do not.

**Check:** `viewer/iXBRLViewerPlugin/viewer/dist/ixbrlviewer.js` exists, and `npm run prod` ends with
`compiled`, possibly "with warnings".

## 3. Inputs

Put each file in `$DEMO/inputs/<folder>/` with the name shown. Those names are what later steps use.

| folder / file | source | sha256 |
|---|---|---|
| `loreal/loreal-2025-12-31-ReportPkg.zip` | [filings.xbrl.org](https://filings.xbrl.org/filing/529900JI1GG6F7RKVI53-2025-12-31-ESEF-FR-0), the report package (download button). Rename it to this name | `e5fab1821620d459d65aeb3f6cbe9ad6bdc08080ca833538fc1e904dcc1afe09` |
| `loreal/LOREAL_DEU_2025_FR.pdf` | [loreal-finance.com](https://www.loreal-finance.com/system/files/2026-03/LOREAL_DEU_2025_FR.pdf), the French Universal Registration Document | `9f95d50ce76adec8cce2378e3393a0d4186976733fc9af1c437bf761bb3a5166` |
| `loreal/loreal.pdf` | **made by hand:** the PDF above, tagged in Acrobat Pro (Accessibility, *Autotag document*), then saved | varies |
| `msft/0000950170-25-100235-xbrl.zip` | [EDGAR](https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/0000950170-25-100235-xbrl.zip), Microsoft's FY2025 10-K | `686c646c38390117a4c85515f3aa585cab888b20612222fe5e2263bbd0e4630a` |
| `msft-ar25/index.html`, `css/`, `fonts/`, `img/` | [microsoft.com/investor/reports/ar25](https://www.microsoft.com/investor/reports/ar25/index.html), Microsoft's annual report web page, saved with its stylesheet and the fonts and images it references (`css/main.css` lists them) | `index.html`: `564154a15ac28c0f7f72f304ae26b74c29cfca9f3eafe8d59595776769d621ca` |
| `paclife/` | [EDGAR filing 0001104659-25-020739](https://www.sec.gov/Archives/edgar/data/813900/000110465925020739/), Pacific Select Fund N-CSR: `tm255536d1_ncsr.htm`, `pacificlife-20241231.xsd` and the images it references | `tm255536d1_ncsr.htm`: `4e9d7a509bb7412c3125ad4435f690c0c0c1581190ff89edee4f0cac4e07679d` |
| `paclife/paclife.pdf` | **made by hand:** `tm255536d1_ncsr.htm` opened in Acrobat Pro with *Create PDF from web page* (tagged) | varies |
| `principal/` | [EDGAR filing 0000898745-24-000723](https://www.sec.gov/Archives/edgar/data/898745/000089874524000723/), Principal Funds N-CSR: the inline primary document as disseminated, saved as `primary-document.htm`, plus `principal-20241031.xsd` and the images it references | `primary-document.htm`: `48f21eb13921236cf205a26830975457c0838c67936b8dd2dab90b32a5bf43dd` |
| `principal/principal.pdf` | **made by hand:** `primary-document.htm` through *Create PDF from web page*, as for Pacific Life | varies |

Notes on the inputs:

- **EDGAR** asks automated clients to identify themselves. Download in a browser, or with
  `curl -A "Your Name you@example.com" -O <url>`.
- **The PDFs must be tagged.** The aligner locates facts by the marked content that tagging creates. An
  untagged PDF locates almost nothing. Tagging output varies with the Acrobat version, so the counts in steps 5
  and 7 may differ slightly from those shown.
- **The Microsoft web page** may answer a script with HTTP 403; save it from a browser. Locators are made
  against the copy you save, so a later revision of the page still works, but the counts can change.
- **The Principal document as disseminated** carries an `ixv-` id on every fact. EDGAR adds these on receipt
  for the SEC's own viewer.

**Check:** `shasum -a 256` of each file matches the table, apart from the hand-made PDFs.

## 4. Settings for the remaining steps

```bash
cd $DEMO && mkdir -p out
export IN=$DEMO/inputs OUT=$DEMO/out
export ALIGN=$DEMO/arelle/arelle/plugin/XbrlModel/tools/alignFactsToSurface.py
export VIEWER_PLUGIN=$DEMO/viewer/iXBRLViewerPlugin
arelle() { local log=$1; shift; rm -f "$log"; python3 $DEMO/arelle/arelleCmdLine.py "$@" --logFile "$log"; }
```

`--saveOIMmodel … --oimSaveMode report` validates the model before saving it, and the log then carries the
validation messages.

**Every model is saved in `report` mode before it is aligned to another rendering.** In that mode the value
stays on each fact, so nothing later has to be re-read from a PDF's or web page's text, which may not parse
back to the filed number.

## 5. L'Oréal: an ESEF report becomes a Tavi model (demo 1), shown on its PDF (demo 2)

```bash
mkdir -p $OUT/loreal && cd $OUT/loreal
arelle report.log --plugins XbrlModel -f $IN/loreal/loreal-2025-12-31-ReportPkg.zip \
    --saveOIMmodel loreal-report.json --oimSaveMode report
arelle pruned.log --plugins XbrlModel -f $IN/loreal/loreal-2025-12-31-ReportPkg.zip \
    --saveOIMmodel loreal-pruned.json --oimSaveMode prune
```

**Check:** in `report.log`, `Loaded 684 facts`. The only findings are six
`oimtce:inconsistentCalculationUsingRounding` for `ifrs-full:ComprehensiveIncome`. These are the same six that
Arelle's own Calculations 1.1 check (`--calc c11r`) reports for this filing. `loreal-pruned.json` is a
self-contained compiled model.

```bash
unzip -q -o $IN/loreal/loreal-2025-12-31-ReportPkg.zip 'loreal-2025-12-31-1-fr/reports/*' -d src
cp $IN/loreal/loreal.pdf .
python3 $ALIGN --html src/loreal-2025-12-31-1-fr/reports/loreal-2025-12-31-1-fr.xhtml \
    --facts loreal-report.json --pdf loreal.pdf --out-facts loreal-pdf.json
```

**Check:** the summary reports `located in PDF .............. 684  (100%)`.

```bash
arelle stage-inline.log --plugins "XbrlModel|$VIEWER_PLUGIN" -f $IN/loreal/loreal-2025-12-31-ReportPkg.zip \
    --saveXbrlModelViewer stage-inline
arelle stage-pdf.log --plugins "XbrlModel|$VIEWER_PLUGIN" -f loreal-pdf.json --saveXbrlModelViewer stage-pdf
```

The inline viewer is staged from the report package itself. Staging expands a package into the documents it
holds, which a model reloaded from JSON cannot do.

**Check:** both logs end with `Staged iXBRL Viewer in …`.

## 6. Microsoft: a 10-K's facts on the company's own web page (demo 2)

```bash
mkdir -p $OUT/msft && cd $OUT/msft
arelle report.log --plugins "XbrlModel|EDGAR/transform" -f $IN/msft/0000950170-25-100235-xbrl.zip \
    --saveOIMmodel msft-report.json --oimSaveMode report
unzip -q -o $IN/msft/0000950170-25-100235-xbrl.zip msft-20250630.htm -d src
cp $IN/msft-ar25/index.html msft-ar25.html
cp -R $IN/msft-ar25/css $IN/msft-ar25/fonts $IN/msft-ar25/img .
python3 $ALIGN --html src/msft-20250630.htm --facts msft-report.json \
    --html5 msft-ar25.html --out-facts msft-html5.json
arelle stage.log --plugins "XbrlModel|EDGAR/transform|$VIEWER_PLUGIN" -f msft-html5.json \
    --saveXbrlModelViewer stage-html5
```

Staging copies the page together with the images, stylesheet, fonts and background images it references,
so the page must sit beside those files as it does here.

**Check:** `report.log` has 21 `oimtce:inconsistentCalculationUsingRounding` findings. The alignment summary
reports `written ..................... as bound derived fact values beside the model` and
`located ..................... 1729  (96%)` of 1,800.

The web page carries no XBRL and no ids on its figures. Each fact is located by an element pointer, a text
offset and a quotation of the text. The placements are written as **derived content** beside the model, which
is left exactly as filed: the person aligning is not the filer, so where somebody else's facts appear is not
part of the filer's model (README §1, `--alignInto`).

## 7. SEC N-CSRs on their PDFs (demo 2)

```bash
for name in paclife principal; do
    htm=$( [ $name = paclife ] && echo tm255536d1_ncsr.htm || echo primary-document.htm )
    mkdir -p $OUT/$name && cd $OUT/$name
    arelle report.log --plugins "XbrlModel|EDGAR/transform" -f $IN/$name/$htm \
        --saveOIMmodel $name-report.json --oimSaveMode report
    cp $IN/$name/$name.pdf .
    python3 $ALIGN --html $IN/$name/$htm --facts $name-report.json --pdf $name.pdf --out-facts $name-pdf.json
    arelle stage.log --plugins "XbrlModel|EDGAR/transform|$VIEWER_PLUGIN" -f $name-pdf.json \
        --saveXbrlModelViewer stage-pdf
done
```

**Check:** in each `report.log`, no findings: Pacific Life `Loaded 36821 facts`, Principal
`Loaded 67151 facts`. The alignment summaries report `36321 (98%)` of 36,706 and `66536 (99%)` of 67,145
located fact values. Most of the facts are located as chart-image regions: a Tailored Shareholder Report
carries its growth-of-$10,000 series in a visually hidden table beside a chart, so the chart is where those
facts appear (README §3). Peak memory is about 3.3 GB and 5.4 GB.

## 8. Prudential templates as Tavi models (demo 3)

Demo 3 generates a Tavi module, with a grid layout per template, from EIOPA's Solvency II DPM annotated
templates workbook (2.8.2 Hotfix). That workbook is not distributed with this guide. Given a copy:

```bash
python3 $DEMO/arelle/arelle/plugin/XbrlModel/tools/tlbTemplate-eiopa.py <workbook.xlsx> $OUT/eiopa.json \
    > $OUT/eiopa-generate.log   # the generator prints its working tables; keep them out of the terminal
arelle $OUT/eiopa.log --plugins XbrlModel -f $OUT/eiopa.json --validate
```

On the 2.8.2 Hotfix workbook used for the demonstration this gives 599 tables (599 report cubes and 393
exclusion cubes for crossed-out cells) with no validation errors. The generator's output is deterministic.

## 9. View

```bash
cd $OUT && python3 -m http.server 8000
```

Open, in a browser:

| demonstration | URL (relative to `http://localhost:8000/`) |
|---|---|
| L'Oréal, the filed inline document | `loreal/stage-inline/ixbrlviewer.html?xbrlModel=loreal-2025-12-31-1-fr-model.json` |
| L'Oréal, the PDF annual report | `loreal/stage-pdf/ixbrlviewer.html?xbrlModel=loreal-2025-12-31-ReportPkg-model.json` |
| Microsoft, the web annual report | `msft/stage-html5/ixbrlviewer.html?xbrlModel=0000950170-25-100235-xbrl-model.json` |
| Pacific Select Fund N-CSR | `paclife/stage-pdf/ixbrlviewer.html?xbrlModel=tm255536d1_ncsr-model.json` |
| Principal Funds N-CSR | `principal/stage-pdf/ixbrlviewer.html?xbrlModel=primary-document-model.json` |

Each staging step's log names its URL. If a name differs, use the one the log gives.

**Check:** facts are highlighted on the document. Selecting one shows its concept, period and value in the
inspector. For example, Microsoft's "Other current liabilities 25,020" on the balance sheet of the web page is
`us-gaap:OtherLiabilitiesCurrent`, US$ 25,020,000,000 at 30 June 2025. The Principal Funds N-CSR, 67,151
facts, opened with facts bound in about 3½ seconds, measured from navigation start with the browser cache
disabled and the files served locally. Your machine will differ.

## 10. The same demonstrations in the Arelle desktop application

On stage the demonstrations run in Arelle's desktop application. It loads, validates and saves models, and opens
the viewer itself. The alignments are made from the command line (steps 5 to 7), so run those steps first: the
desktop application then opens the models they produced.

**Start Arelle and enable the plugins (once).**

```bash
cd $DEMO/arelle && . ../.venv/bin/activate && python3 arelleGUI.pyw
```

In **Help ▸ Manage plug-ins**, add three plugins:

| plugin | how to add it | listed as |
|---|---|---|
| XBRL Model | **Select**, then `XbrlModel` | XBRL Model |
| SEC transforms | **Select**, then `EDGAR` (simplest), or **Browse**, then `$DEMO/arelle/arelle/plugin/EDGAR/transform/__init__.py` | EDGAR, or SEC Inline Transforms |
| viewer | **Browse**, then `$DEMO/viewer/iXBRLViewerPlugin/__init__.py` | ixbrl-viewer |

Selecting the whole `EDGAR` plugin brings in the transforms with the rest of it, and logs
`[arelle.xulePluginNotLoaded] Xule plugin is not loaded`, which is harmless here: XULE runs the DQC rules,
which these steps do not use. Browsing to `EDGAR/transform/__init__.py` adds only the transforms.

Close the dialog and restart Arelle. Restart it again whenever the code under `$DEMO` is updated: a running
Arelle keeps the plugin code it loaded.

**Check:** **Help ▸ Manage plug-ins** lists all three as `enabled`, and the **Tools** menu has
**Open iXBRL Viewer on load** (checked) and **Validate XBRL model on load** (checked).

**Demo 1: an ESEF report becomes a Tavi model.** Open `$IN/loreal/loreal-2025-12-31-ReportPkg.zip` with
**File ▸ Open File…**. Arelle loads the package, compiles the taxonomy and facts into one model and validates
it. It then replaces the usual taxonomy views with the model's own: **Groups** (the report's sections),
**Concepts**, **Cubes**, **Networks**, **Domain Networks** and the facts. Select a row and the
**Properties** and **JSON** panes show that object.

**Check:** the messages pane shows the six `oimtce:inconsistentCalculationUsingRounding` findings from step 5.

Then save the self-contained model with **File ▸ Save**, choosing `prune` in the save-mode dialog. The
viewer also opens in the browser on the filed inline document; see the next paragraph.

**Demo 2: one fact, every surface.** Open each aligned model in turn with **File ▸ Open File…**:

| model | the viewer shows |
|---|---|
| `$OUT/loreal/loreal-pdf.json` | L'Oréal's PDF annual report |
| `$OUT/msft/msft-html5.json` | Microsoft's web annual report |
| `$OUT/paclife/paclife-pdf.json` | the Pacific Select Fund N-CSR PDF |
| `$OUT/principal/principal-pdf.json` | the Principal Funds N-CSR PDF |

For each, Arelle validates the model, then stages a viewer in a folder named `out` beside the model and
opens it in the browser from a small local web server. The folder holds the model, the documents it names,
and the viewer. The documents are copied from beside the model, which is where steps 5 to 7 leave them.
**Tools ▸ View XBRL model in iXBRL Viewer** opens it again. Loading the largest model takes about a minute
before the browser opens.

**Check:** each opens with facts highlighted, as in step 9, and the browser's console shows no failed
requests. Microsoft's page is styled as on microsoft.com: its stylesheet, fonts and images are staged with
it. An unstyled page, or console 404s for `ixbrlviewer.config.json` or `main.css`, means an Arelle started
before the code was updated: restart it.

**Demo 3: prudential templates.** Open `$OUT/eiopa.json`. The **Cubes** pane holds one cube per template table
(599); the grid layouts are the `layouts` object of `eiopa.json`, one data table per template. The module
has no facts or source document, so no viewer opens. Loading and building the views for its 992 cubes takes a
little while.

## What these steps do not cover

The Tavi PWD is published at [specifications.xbrl.org](https://specifications.xbrl.org/under-development.html).
Its conformance tests are working-group material, and these steps do not use them. Everything above uses only
public filings, public code and the hand-made PDFs described in step 3.
