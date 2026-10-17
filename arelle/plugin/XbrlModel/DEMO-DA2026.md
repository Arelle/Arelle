<!-- See COPYRIGHT.md for copyright information. -->

# Reproducing the Data Amplified 2026 demonstration

These steps rebuild the demonstration "From today's filings to Tavi: an independent prototype in Arelle"
(Data Amplified, The Hague, 2026) from the published filings. They load reports filed today, validate the
compiled Tavi models, and stage a viewer that shows each filing's facts on a second rendering of the same
report: the company's PDF annual report, or its published web page. For prudential reporting, which has no
document of its own, they generate Tavi models of EIOPA's Solvency II templates from EIOPA's published
workbook, attach the facts of EIOPA's published sample reports, and show those facts in the templates.

**What this is.** The XBRL Model plugin is a working prototype on an Arelle branch, built by Herm Fischer
while helping to draft the Tavi Public Working Draft (PWD). It is not Arelle production code, and it is not
supported by Workiva or the Arelle team. Some of what it does is defined by the PWD: the model, its validation
and its fact maps. The rest is prototype work built on top of it: loading legacy filings, derived content,
aligning facts to other renderings, and the viewer overlay. See [README.md](README.md).

What each part of the demonstration rests on, labelled as in the two pull requests:

| | what |
|---|---|
| **PWD** (the Tavi Public Working Draft, 2026-09-01) | the model, its validation and fact maps; fact value locators on XHTML and PDF documents; the layout objects (grid layout data tables) the templates are drawn from |
| **tooling** (implements no specification beyond the PWD) | compiling legacy ESEF and SEC filings into Tavi models; aligning their facts to a PDF or web page; staging the viewer; the viewer overlay and its table surface; the EIOPA template generator and sample-fact converter |
| **research** (the author's proposals, not part of the PWD, not adopted by XBRL International) | positional locators for HTML without ids; derived content (verdicts recorded by the processor); where the PWD leaves a layout point open, the reading used here: what a grid header's `span` counts, and axis groups as an open table's key columns and as z selections |

The EIOPA models put every object in one `eiopa:` namespace, keeping the source prefix in the local name
(`s2md_met:mi686` becomes `eiopa:s2md_met_mi686`), because a module may define objects only in its own
namespace. A production model would instead use EIOPA's own dictionaries; this is a workaround for the
demonstration, not a proposal.

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
| `eiopa-2.10/EIOPA_Solvency_II_DPM_Annotated_Templates_2.10.0.xlsx` | [EIOPA](https://dev.eiopa.europa.eu/Taxonomy/Full/2.10.0/S2/EIOPA_Solvency_II_DPM_Annotated_Templates_2.10.0.xlsx), the Solvency II 2.10.0 DPM annotated templates, from [EIOPA's supervisory reporting page](https://www.eiopa.europa.eu/tools-and-data/supervisory-reporting-dpm-and-xbrl_en) | `518980394e10913a68240238b65123f5bd4f2df5dffe56365a284c9388cbd0e6` |
| `eiopa-2.10/EIOPA_SolvencyII_XBRL_Instance_documents_2.10.0.zip` | [EIOPA](https://dev.eiopa.europa.eu/Taxonomy/Full/2.10.0/S2/EIOPA_SolvencyII_XBRL_Instance_documents_2.10.0.zip), EIOPA's sample XBRL 2.1 reports for every Solvency II entry point, with random and zero values, from the same page | `31494f7a34dd03399002a33abc0d07df87ba6d927c74ce4d8dbea81a4297e7e2` |
| `tavi-demo/tavi-demo-2026-09-01.zip` | [xbrl.org](https://www.xbrl.org/Specification/tavi/PWD-2026-09-01/demo/tavi-demo-2026-09-01.zip), the Tavi PWD's published demo, whose model viewer shows the generated templates as tables (step 8) | `4518c96461d7538953834d7506ad31a352023eb7a15ea7438f730adb8455d394` |
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

## 8. Prudential templates as Tavi models, with EIOPA's sample data (demo 3)

Demo 3 generates a Tavi module, with a grid layout per template, from EIOPA's Solvency II DPM annotated
templates workbook, release 2.10.0, and attaches the facts of EIOPA's own sample reports to it (step 3), so
the templates can be read with data in them.

**The templates.**

```bash
export EIOPA=$DEMO/arelle/arelle/plugin/XbrlModel/tools
mkdir -p $OUT/eiopa && cd $OUT/eiopa
python3 $EIOPA/tlbTemplate-eiopa.py $IN/eiopa-2.10/EIOPA_Solvency_II_DPM_Annotated_Templates_2.10.0.xlsx \
    eiopa.json > generate.log   # the generator prints its working tables; keep them out of the terminal
arelle validate.log --plugins XbrlModel -f eiopa.json --validate
```

**Check:** `generate.log` has the lines `Z axis groups: 393, member lists unmatched: 0 []` and
`Num tables 572, …`. `validate.log` has no message other than `[info]` lines. The module has 570 data tables
(two sheets of the workbook are not templates), 570 report cubes and 556 exclusion cubes for crossed-out
cells. The generator's output is deterministic.

**The sample data.** EIOPA publishes a sample report for every entry point, as XBRL 2.1 instances against its
own taxonomy. The converter reads an instance as plain XML (the EIOPA taxonomy is not needed), renames its
concepts, dimensions and members onto the generated module's names, and attaches the facts whose concept,
dimensions and members the module defines:

```bash
unzip -q -o $IN/eiopa-2.10/EIOPA_SolvencyII_XBRL_Instance_documents_2.10.0.zip -d samples
SAMPLES=samples/EIOPA_SolvencyII_XBRL_Instance_documents_2.10.0/random
python3 $EIOPA/eiopaInstanceFacts.py $SAMPLES/ars_2026-06-30_instance.xbrl eiopa-ars.json eiopa.json
python3 $EIOPA/eiopaInstanceFacts.py $SAMPLES/qrs_2026-06-30_instance.xbrl eiopa-qrs.json eiopa.json
arelle validate-ars.log --plugins XbrlModel -f eiopa-ars.json --validate
arelle validate-qrs.log --plugins XbrlModel -f eiopa-qrs.json --validate
```

`ars` is the annual return of a solo undertaking, `qrs` its quarterly return.

**Check:** the converter prints `21191 of 26234 facts have a concept, dimensions and members of
eiopa:eiopaExample` for `ars` and `1021 of 1109 …` for `qrs`. `validate-qrs.log` has no message other than
`[info]` lines: every quarterly fact fits a template's cube. `validate-ars.log` has 176
`oimte:noFactSpaceForFact` and nothing else: those annual facts fit no generated cube, which is where the
generated layouts still miss something. The facts left out by the converter use dimensions or members the
workbook does not name.

**A template on its own.** For a quick look, generate one template and attach the quarterly facts:

```bash
python3 $EIOPA/tlbTemplate-eiopa.py $IN/eiopa-2.10/EIOPA_Solvency_II_DPM_Annotated_Templates_2.10.0.xlsx \
    S.02.01.01.01.json S.02.01.01.01 > generate-S.02.01.log
python3 $EIOPA/eiopaInstanceFacts.py $SAMPLES/qrs_2026-06-30_instance.xbrl S.02.01.01.01-qrs.json S.02.01.01.01.json
```

**Check:** `81 of 1109 facts have a concept, dimensions and members of eiopa:eiopaExample`.

**The templates with their data, in the viewer.** A model with grid layouts and no document of its own is
shown by the viewer overlay as its tables:

```bash
arelle stage.log --plugins "XbrlModel|$VIEWER_PLUGIN" -f eiopa-ars.json --saveXbrlModelViewer stage-tables
arelle stage-S.02.01.log --plugins "XbrlModel|$VIEWER_PLUGIN" -f S.02.01.01.01-qrs.json \
    --saveXbrlModelViewer stage-S.02.01
```

**Check:** each log has `Staged iXBRL Viewer in …; serve it and open
ixbrlviewer.html?xbrlModel=…-model.json`. Staging validates the model first, so `stage.log` repeats the 176
`oimte:noFactSpaceForFact` of `validate-ars.log`. A `[viewer:exception] iXBRL Viewer destination not
provided` line is the viewer plugin's own command-line hook, and is harmless. Step 9 opens them.

**The layouts alone, in the PWD's published viewer.** The model viewer of the PWD's published demo draws a
module's grid layouts in its **Layout** tab. Generate a template on its own, without facts, into a copy of
that demo:

```bash
unzip -q -o $IN/tavi-demo/tavi-demo-2026-09-01.zip -d .
python3 $EIOPA/tlbTemplate-eiopa.py $IN/eiopa-2.10/EIOPA_Solvency_II_DPM_Annotated_Templates_2.10.0.xlsx \
    tavi-demo-2026-09-01/examples/eiopa-S.02.01.01.01.json S.02.01.01.01 > generate-pwd-S.02.01.log
```

Open that viewer (step 9), use **Open File…** to choose `examples/eiopa-S.02.01.01.01.json`, select the
**Layout** tab, then the layout `eiopa:eiopaLayout`. **Check:** S.02.01.01.01, the balance sheet, is drawn
with its Assets and Liabilities bands, the nested categories beneath them, 83 rows from R0010 (goodwill) to
R1000 (excess of assets over liabilities), and the columns C0010 (Solvency II value) and C0020 (statutory
accounts value).

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
| EIOPA Solvency II templates, with the annual sample's facts | `eiopa/stage-tables/ixbrlviewer.html?xbrlModel=eiopa-ars-model.json` |
| EIOPA S.02.01.01.01 balance sheet, with the quarterly sample's facts | `eiopa/stage-S.02.01/ixbrlviewer.html?xbrlModel=S.02.01.01.01-qrs-model.json` |

Each staging step's log names its URL. If a name differs, use the one the log gives.

The PWD demo viewer of step 8 is `eiopa/tavi-demo-2026-09-01/viewer/model-viewer.html` under the same address.

**Check:** facts are highlighted on the document. Selecting one shows its concept, period and value in the
inspector. For example, Microsoft's "Other current liabilities 25,020" on the balance sheet of the web page is
`us-gaap:OtherLiabilitiesCurrent`, US$ 25,020,000,000 at 30 June 2025. The Principal Funds N-CSR, 67,151
facts, opened with facts bound in about 3½ seconds, measured from navigation start with the browser cache
disabled and the files served locally. Your machine will differ.

**Check, EIOPA:** the page lists the templates that have data, each drawn as a table, with a sheet for each
Z axis selection the data uses (for S.25.01.01.01, Article 112: Yes). Selecting a cell shows its fact in the
inspector: S.02.01.01.01's R0050 (pension benefit surplus), C0010 (Solvency II value) is
`eiopa:s2md_met_mi256`, € -155 at 31 December 2026, Valuation general: Solvency II. **Next** and **Previous**,
the **Search** results and the **Cubes** list each select and scroll to their cell. The whole annual sample
(383 templates with data, 21,703 cells) opened with its facts bound in about 2.7 seconds, the balance sheet
alone in under a second. EIOPA's sample entity `ABCDEFGHIJ0123456789` is not a valid LEI (it fails the
ISO 17442 checksum); that is the sample's data, not a fault.

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

**Demo 3: prudential templates.** Open `$OUT/eiopa/S.02.01.01.01-qrs.json`, then `$OUT/eiopa/eiopa-ars.json`.
Arelle validates each model and shows its **Cubes** (a report cube per template, and exclusion cubes for
crossed-out cells) and its facts. The model has grid layouts and no document, so the viewer opens on the
templates as tables, as in step 9. Loading and building the views for the whole workbook's 1,126 cubes and
21,191 facts takes a little while before the browser opens. `$OUT/eiopa/eiopa.json`, the module without
facts, opens in Arelle with no viewer: there is nothing to show in its tables.

**Check:** as in step 9, EIOPA. If the browser shows "No source document specified", the viewer plugin is
older than this code: update `$DEMO/viewer`, rebuild it (step 2) and restart Arelle.

## What these steps do not cover

The Tavi PWD is published at [specifications.xbrl.org](https://specifications.xbrl.org/under-development.html).
Its conformance tests are working-group material, and these steps do not use them. Everything above uses only
public filings, public code and the hand-made PDFs described in step 3.
