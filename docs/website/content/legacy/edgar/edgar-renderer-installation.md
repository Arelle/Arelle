---
# Compatibility-only SEC-linked page; see _index.md before moving or removing.
title: Quick Start to Install EDGAR® Renderer
url: /arelle/pub/edgar-renderer-installation/
aliases:
  - /edgar-renderer-installation/
  - /arelle/edgar-renderer-installation/
build:
  list: never
sitemap:
  disable: true
---

Several alternative installation strategies can be followed:

1. Install a pre-built application. These are available with embedded Python and require no developer skills.
2. Install from sources on GitHub. ([See Technical Operation][technical-operation])

Once installed there are two strategies for using the EDGAR renderer:

1. Interactively from its GUI. (This now includes a local viewer using the same components as the sec.gov website.)
2. Technical Operation: from command line, as a web service, or polled operation as a daemon service. ([See Technical Operation][technical-operation])

## Installing

### Pre-built application

Pre-built applications for Windows, macOS and Linux are on the [Arelle download page][download-page], which offers each build from the US, EU and CN mirrors.

- Download and install.
  - It isn't necessary to remove old versions first.
  - If you don't have administrator rights on your computer, install to a directory that you do have rights to (such as under Documents).

## User Operation

### Interactively from its GUI

Start Arelle with the installed app, from the Windows start menu or by clicking on arelleGUI.exe, or with the Mac Application Arelle.app.

{{< image src="start-1.png" alt="start Edgar Renderer Windows" width="221" caption="Starting Arelle from the Windows Start menu." >}}

{{< image src="start-2.png" alt="start Edgar Renderer Mac" width="240" caption="Starting Arelle on macOS." >}}

Check that the EDGAR renderer plugin is installed and enabled: help→manage plugins.

{{< image src="plugin-1b.png" alt="manage plugins" width="267" caption="Arelle's Manage Plugins dialog." >}}

If EDGAR Renderer is not shown, press Select→EDGAR Renderer→ok→close.

{{< image src="plugin-2.png" alt="select Edgar Renderer" width="504" caption="Selecting the EDGAR Renderer plugin." >}}

Click yes when asked to restart.

{{< image src="plugin-3.png" alt="allow to restart" width="507" caption="Confirming the Arelle restart." >}}

If behind a firewall with Microsoft NTLM proxy service (common in large enterprises), also install the internet proxy plugin for NTLM (help→manage plugins→select→Internet NTLM proxy handler→ok→close).

{{< image src="plugin-4.png" alt="select NTLM proxy plugin" width="360" caption="Selecting the Internet NTLM proxy handler." >}}

It may be necessary to start your browser and open a public website (such as Google) to "prime" NTLM for your user account, before Arelle can access the outside internet.

For validation using EDGAR Filer Manual, Tools→Validation→Select Disclosure System.

{{< image src="enable-validation-1.png" alt="select disclosure system" width="341" caption="Selecting the EDGAR disclosure system." >}}

Select an EDGAR Filing Manual validation mode, such as Pragmatic, and press ok.

{{< image src="enable-validation-2.png" alt="select EDGAR Filer Manual validation mode" width="373" caption="Choosing an EDGAR Filer Manual validation mode." >}}

Enable Disclosure system checks. This menu entry is a checkmark toggle; click so it is enabled.

{{< image src="enable-validation-3.png" alt="check menu selection for disclosure system validation" width="333" caption="Enabling disclosure system checks." >}}

Open an SEC filing with the Open File toolbar button, then select the instance document or inline html document. After successful loading the local viewer should display the SEC rendering engine results. If it's an inline html document, click the (Source) top menu entry to see the html form with fact information highlighted by ixviewer.

{{< image src="toolbarOpenFile.png" alt="open file toolbar button" caption="The Open File toolbar button." >}}

{{< image src="select-menu.png" alt="inline ix viewer" width="317" caption="The inline XBRL viewer." >}}

Redline markups in the inline document set are now shown with the View menu selection "Workstation Redline Mode". (These markups are a private communication from filer to SEC personnel, for SEC workstations upon request. They are not disseminated to the public.)

For filer manual validation, use the Validate toolbar button.

{{< image src="toolbarValidate.png" alt="validate toolbar button" caption="The Validate toolbar button." >}}

[download-page]: /download
[technical-operation]: /legacy/edgar/edgar-renderer-technical-operation
