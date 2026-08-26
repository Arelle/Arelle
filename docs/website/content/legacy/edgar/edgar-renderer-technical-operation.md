---
# Compatibility-only SEC-linked page; see _index.md before moving or removing.
title: EDGAR® Renderer Technical Operation
url: /arelle/pub/edgar-renderer-installation/edgar-renderer-technical-operation/
aliases:
  - /edgar-renderer-technical-operation/
  - /arelle/edgar-renderer-technical-operation/
  - /arelle/pub/edgar-renderer-technical-operation/
  - /documentation/edgar-renderer-technical-operation/
  - /arelle/documentation/edgar-renderer-technical-operation/
build:
  list: never
sitemap:
  disable: true
---

Several alternative installation strategies can be followed:

1. Install a pre-built application. ([See Quick Start][quick-start])
2. Install from sources on GitHub.

Once installed there are three strategies for using the EDGAR renderer:

1. Interactively from its GUI. ([See Quick Start][quick-start])
2. Technical Operation:
   1. From command line. (Can be integrated into your preparation environment.)
   2. As a web service. (Can use the built-in web service.)
   3. Polled operation as a daemon service.

## Installing

### Pre-built application

([See Quick Start][quick-start])

### From GitHub sources

Please install the following components on your platform:

- Python 3.12 from python.org or other
- Arelle® [source code on GitHub (master branch suggested)][arelle-source]
- EDGAR Renderer [source code on GitHub (master branch suggested)][edgar-source]. Suggested installation location is under Arelle's plugin directory — `{installed Arelle location}/arelle/plugin/EdgarRenderer`

## User Operation

### Interactively from its GUI

([See Quick Start][quick-start])

### Command line operation

Try "about" to see if it loads correctly.

Windows pre-built app:

```text
arelleCmdLine -a
```

Mac app:

```text
Arelle.app/Contents/MacOS/arelleCmdLine -a
```

Windows from GitHub sources:

```text
python arelleCmdLine.py -a
```

macOS from GitHub sources:

```text
python3 arelleCmdLine.py -a
```

Try help (showing flags only):

```text
{arelle} -h
```

Load inline XBRL /somewhere/myTest.htm, validate, and put rendering output results to /somewhere/out, also copying the source document to output for ixviewer:

```text
{arelle} -f /somewhere/myTest.htm --plugins EdgarRenderer --disclosureSystem efm-pragmatic --validate -r /somewhere/out
```

The `-r` out directory is cleared on each run to assure no remaining files from a prior run may be intermixed. Please don't point the `-r` out directory to a shared location.

The `-f` parameter may be a zip file, in which case all the instances detected in the root directory of the zip are processed.

The `-f` parameter may be a JSON structure (as used in EDGAR itself) to pass in more information about the filing (see `validate/EFM/__init__.py`) such as:

- for a single instance filing, such as an SDR K form (without `\n`'s pretty printed below):

  ```text
  -f '[{"file": "/Users/joe/.../gpc_gd1-20130930.htm",
  "cik": "0000350001",
  "cikNameList": {"0001306276":"BIGS FUND TRUST CO"},
  "submissionType":"SDR-A",
  "exhibitType":"EX-99.K SDR.INS",
  "accessionNumber":"0001125840-15-000159"}]'
  ```

- for multiple instances (SDR-L's), add more of the `{"file": ...}` entries.
- for inline XBRL document sets (IXDSes) of possibly multiple documents per IXDS entry:

  ```text
  --file '[{"ixds":[{"file":file1,"documentType":"6-K"},{"file":file2,"documentType":"EX-99.1"}...],"cik":"0000350001","submissionType":"6-K",...}]'
  ```

  DocumentType may be specified per file and the rest of the parameters per ixds.
- for Windows called from Java, the JSON must be quoted as thus:

  ```text
  -f "[{\"file\":\"z:\\Documents\\...\\gpc_gd1-20130930.htm\",
  \"cik\": \"0000350001\",
  \"cikNameList\": {\"0000350001\":\"BIG FUND TRUST CO\"},
  \"submissionType\":\"SDR-A\", \"exhibitType\":\"EX-99.K SDR.INS\"}]"
  ```

The file parameter JSON structure may pass in EDGAR Link Online (ELO) parameters to perform the same validation as EDGAR does with submission parameters:

```text
[ {# current fields in JSON structure from Arelle Wrapper, per instance
"file": "file path to instance or html",
"cik": "1234567890",
"cikNameList": { "cik1": "name1", "cik2":"name2", "cik3":"name3"...},
"submissionType" : "SDR-A",
"exhibitType": "EX-99.K",
"itemsList": [] # array of items, e.g. ["5.03"] (either array of strings blank-separated items in string)
"accessionNumber":"0001125840-15-000159" ,
# new fields
"periodOfReport": "mm-dd-yyyy",
"entityRegistration.fyEnd": "mm/dd", # the FY End value from entity (CIK) registration
"entity.repFileNum": file number from entity (CIK) registration
"submissionHeader.fyEnd": "mm/dd", # the FY End value from submission header
"voluntaryFilerFlag": true/false, # JSON Boolean, string Yes/No, yes/no, Y/N, y/n or absent
"wellKnownSeasonedIssuerFlag": true/false, # JSON Boolean, string Yes/No, yes/no, Y/N, y/n or absent
"shellCompanyFlag": true/false, true/false, # JSON Boolean, string Yes/No, yes/no, Y/N, y/n or absent
"acceleratedFilerStatus": true/false, # JSON Boolean, string Yes/No, yes/no, Y/N, y/n or absent
"smallBusinessFlag": true/false, # JSON Boolean, string Yes/No, yes/no, Y/N, y/n or absent
"emergingGrowthCompanyFlag": true/false, # JSON Boolean, string Yes/No, yes/no, Y/N, y/n or absent
"exTransitionPeriodFlag": true/false, # JSON Boolean, string Yes/No, yes/no, Y/N, y/n or absent
# filer - use "cik" above
"invCompanyType": "N-1A" # from table of investment company types
"rptIncludeAllSeriesFlag": true/false, # JSON Boolean, string Yes/No, yes/no, Y/N, y/n or absent
"rptSeriesClassInfo.seriesIds": ["S0000990666", ...] # list of EDGAR seriesId values
"newClass2.seriesIds": [] # //seriesId xpath result on submission headers
# CEF forms
"eligibleFundFlag": true/false, # JSON Boolean, string Yes/No, yes/no, Y/N, y/n or absent
"pursuantGeneralInstructionFlag": true/false, # JSON Boolean, string Yes/No, yes/no, Y/N, y/n or absent
"filerNewRegistrantFlag": true/false, # JSON Boolean, string Yes/No, yes/no, Y/N, y/n or absent
# Test/debug fields
datetimeForTesting: xml-syntax datetime to override clock time for test/debug purposes
},
{"file": "file 2"...
]
```

Note that JSON Boolean objects (true/false) do not have quotation marks.

Further details of instructions are in the comments to `plugin/EdgarRenderer/__init__.py` and `plugin/validate/EFM/__init__.py`.

### Web service operation

You may use the built-in web server or install to Apache/CGI or IIS/CGI (see documentation — API Web Services).

To start the built-in web server, Windows pre-built app:

```text
arelleCmdLine --webserver localhost:8080
```

Mac app:

```text
Arelle.app/Contents/MacOS/arelleCmdLine --webserver localhost:8080
```

To test that it is operating, from a browser: `http://localhost:8080/about`. For help: `http://localhost:8080/help`.

To run a validation on a zip file containing the instance document and linkbases:

```text
curl -X POST "-HContent-type: application/zip"
-T myInstanceAndLinkbases.zip
-o edgarRendererResultsOutput.zip
"http://localhost:8080/rest/xbrl/validation?efm-pragmatic&media=zip&plugins=EdgarRenderer&logFile=log.xml"
```

The log file of messages and errors will be in the zip as "log.xml" in xml format (or .txt or .json, as you wish).

The input file (posted by web service request) may be a zip file, in which case all the instances detected in the zip file's root directory are processed.

### Redline markups in inline XBRL documents

When viewing FilingSummary.htm in a browser, add the parameter `?redline=true` to enable viewing redline markups on filings before submission to SEC. (These are a private communication from filer to SEC which are not disseminated to the public.)

### Polled operation as a daemon service

See directory `plugin/EdgarRenderer/svc_template`. Batch scripts BuilderService.bat and .sh start a polling application, which looks for input zip files in a subdirectory Filings, processes each instance detected in the zip file root directory, puts results in Reports, archives input in Archive, and errors to Errors.

## Prior instructions for EDGAR and a polling-based operation

This section will be deleted in a future update.

### Install Python 3.4.2, its libraries, and Arelle

Retrieve the file install-python-3.4.2-arelle-windows.zip. You can either save it, or simply open it and unzip it to a convenient location such as your Desktop.

Inside the folder is a batch script file **install-for-rendering-engine.bat**; double-click on it to run it.

The script will ask you to press "y" or "Enter" before proceeding with each step. It will also notify you of errors or warnings that you can safely ignore.

The first operation will run an installation dialog for Python 3.4.2.

(The prompt, Press "ignore" to "Could not update environment variable PathExt", expects you to press enter. On some systems (Windows 10 on Parallels on Mac) you may need to press enter more than one time for the Python installation dialog to start up.)

The Python installation dialog will present you with choices and a "Next >" button. We suggest these settings:

- Select whether to install Python 3.4.2 (64-bit) for all users of this computer. Choose "Install for all users", then click Next >.
- Select Destination Directory: keep the default, which is `c:\Python34`, then click Next >.
- Customize Python 3.4.2 (64-bit):

  | Option | Setting |
  | --- | --- |
  | Register Extensions | yes |
  | Tcl/Tk | yes |
  | Documentation | no |
  | Utility scripts | yes |
  | Pip | yes |
  | Test Suite | yes |
  | Add python.exe to Path | no |

  Then click Next >.
- Installation will run for a few moments. Click Finish.

After the Python installation dialog finishes, the underlying DOS command prompt window should reappear and be active with the prompt "Press any key to continue". You're not done yet — please press the enter/return key.

### Install the EDGAR Renderer

The `edgar_renderer_3_3_0_814.zip` distribution described below is no longer published. Use the current EDGAR Renderer from the [Arelle/EDGAR repository][edgar-source] instead. The remainder of this section is retained as a record of how that distribution was laid out.

Retrieve the file edgar_renderer_3_3_0_814.zip and extract its contents to the "c:" drive. This will create these folders:

```text
c:\re3\arelle
c:\re3\edgarrenderer
c:\re3\resources
c:\re3\samples
c:\re3\svc_template
```

and two batch scripts:

```text
c:\re3\EdgarRenderer.bat
c:\re3\RunSamples.bat
```

Double-click on the batch script `c:\re3\RunSamples.bat`; if everything is working correctly, it will run the EdgarRenderer.bat program on three sample XBRL filings that have been provided in the samples folder. Their outputs will be in these folders:

```text
c:\re3\samples\alfalfa\Reports\
c:\re3\samples\edgar-2015\Reports\
c:\re3\samples\multiline\Reports\
```

As the RunSamples.bat script illustrates, you run EdgarRenderer with a `-f` argument that is either an XBRL instance, a zip file containing an XBRL instance and other files, or any folder containing XBRL files.

Go to a command shell and run this command to see all of the arguments to the program:

```text
c:\re3\EdgarRenderer.bat --help | more
```

## Contact and Support

End user support is by e-mail direct to SEC at: <StructuredData@sec.gov>

[arelle-source]: https://github.com/Arelle/Arelle
[edgar-source]: https://github.com/Arelle/EDGAR
[quick-start]: /legacy/edgar/edgar-renderer-installation
