;Arelle Installer User Interface
;Adapted from Basic Example Script
;Written by Joost Verburg
;Tailored for Arelle 2011-04-28
; Preprocessor 

!define APP_NAME "Arelle"

!define ARELLE_UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arelle"

!define UNINSTALLER "$INSTDIR\Uninstall.exe"

; Version passed in at build time via /DINSTALLER_VERSION=x.y.z.n /DAPP_VERSION=x.y.z
!ifndef INSTALLER_VERSION
  !define INSTALLER_VERSION "0.0.0.0"
!endif

!ifndef APP_VERSION
  !define APP_VERSION "0.0.0"
!endif

;--------------------------------
;Include Modern UI

  !include "MUI2.nsh"

;--------------------------------
;General

  ;Name and file
  Name "Arelle"


  Icon arelle\images\arelle.ico
  UninstallIcon arelle\images\arelle.ico



  ; VIProductVersion must be four dot-separated non-negative integers: major.minor.patch.build
  VIProductVersion "${INSTALLER_VERSION}"

  ; Version of the installer (stays consistent with VIProductVersion)
  VIAddVersionKey "FileDescription" "${APP_NAME} Windows Installer"
  VIAddVersionKey "FileVersion" "${INSTALLER_VERSION}"

  ; Version of Arelle that we're installing.
  VIAddVersionKey "ProductName" "${APP_NAME}"
  VIAddVersionKey "ProductVersion" "${APP_VERSION}"

  VIAddVersionKey "CompanyName" "Workiva, Inc."
  VIAddVersionKey "LegalCopyright" "Copyright © 2011-present Workiva, Inc."
  OutFile "dist\arelle-win-x64.exe"

  ; Admin rights are required to write to HKLM and $PROGRAMFILES64
  RequestExecutionLevel admin

  ;Default installation folder
  InstallDir "$PROGRAMFILES64\Arelle"
  
  ;Get installation folder from registry if available
  InstallDirRegKey HKLM "Software\Arelle" ""

;--------------------------------
;Variables

  Var StartMenuFolder

;--------------------------------
;Interface Settings

  !define MUI_ABORTWARNING

;--------------------------------
;Pages

  !insertmacro MUI_PAGE_LICENSE "LICENSE.md"
  ; !insertmacro MUI_PAGE_COMPONENTS
  !insertmacro MUI_PAGE_DIRECTORY
  
  ;Start Menu Folder Page Configuration
  !define MUI_STARTMENUPAGE_REGISTRY_ROOT "HKLM" 
  !define MUI_STARTMENUPAGE_REGISTRY_KEY "Software\Arelle" 
  !define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "Start Menu Folder"
  
  !insertmacro MUI_PAGE_STARTMENU Application $StartMenuFolder
  
  !insertmacro MUI_PAGE_INSTFILES
  
  !insertmacro MUI_UNPAGE_CONFIRM
  !insertmacro MUI_UNPAGE_INSTFILES
  
;--------------------------------
;Languages
 
  !insertmacro MUI_LANGUAGE "English"

;--------------------------------
;Installer Sections

Section "Arelle" SecArelle

  SetOutPath "$INSTDIR"

  ;CLEAN INSTALL DIRECTORY
  Delete "$INSTDIR\*.*"

  RMDir /r "$INSTDIR\*"
  
  ;ADD YOUR OWN FILES HERE...
  File /r $%BUILD_PATH%\*.*
  
  ;Store installation folder
  WriteRegStr HKLM "Software\Arelle" "" $INSTDIR
  ; Write the essential uninstall keys for Windows
  WriteRegDWORD HKLM  "${ARELLE_UNINSTALL_KEY}" "NoModify"          1
  WriteRegDWORD HKLM  "${ARELLE_UNINSTALL_KEY}" "NoRepair"          1
  WriteRegStr   HKLM  "${ARELLE_UNINSTALL_KEY}" "UninstallString"   '"${UNINSTALLER}"'

  ; Add the other metadata too
  WriteRegStr   HKLM  "${ARELLE_UNINSTALL_KEY}" "DisplayIcon"       "$INSTDIR\images\arelle.ico"
  WriteRegStr   HKLM  "${ARELLE_UNINSTALL_KEY}" "DisplayName"       "${APP_NAME}"
  WriteRegStr   HKLM  "${ARELLE_UNINSTALL_KEY}" "DisplayVersion"    "${APP_VERSION}"

  WriteRegStr   HKLM  "${ARELLE_UNINSTALL_KEY}" "HelpLink"          "https://groups.google.com/d/forum/arelle-users"
  WriteRegStr   HKLM  "${ARELLE_UNINSTALL_KEY}" "Publisher"         "arelle.org"
  WriteRegStr   HKLM  "${ARELLE_UNINSTALL_KEY}" "RegOwner"          "Workiva, Inc."
  WriteRegStr   HKLM  "${ARELLE_UNINSTALL_KEY}" "URLInfoAbout"      "https://arelle.org"
  WriteRegStr   HKLM  "${ARELLE_UNINSTALL_KEY}" "URLUpdateInfo"     "https://github.com/Arelle/Arelle/releases"







  ; Create uninstaller
  WriteUninstaller "${UNINSTALLER}"
  
  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
    
    ;Create shortcuts
    CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
    CreateShortCut "$SMPROGRAMS\$StartMenuFolder\Arelle.lnk" "$INSTDIR\arelleGUI.exe"

    ; check if webserver installed (known to be there if QuickBooks.qwc is in the build)
    IfFileExists "$INSTDIR\QuickBooks.qwc" 0 +2
        CreateShortCut "$SMPROGRAMS\$StartMenuFolder\Start Web Server.lnk" "$INSTDIR\arelleCmdLine.exe" "--webserver localhost:8080"

    CreateShortCut "$SMPROGRAMS\$StartMenuFolder\Uninstall.lnk" "${UNINSTALLER}"
  
  !insertmacro MUI_STARTMENU_WRITE_END

SectionEnd

;--------------------------------
;Descriptions

  ;Language strings
  LangString DESC_SecArelle ${LANG_ENGLISH} "Arelle Windows x64 installation.  Includes Python and tcl modules needed for operation."

  ;Assign language strings to sections
  ; !insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  ;   !insertmacro MUI_DESCRIPTION_TEXT ${SecArelle} $(DESC_SecArelle)
  ; !insertmacro MUI_FUNCTION_DESCRIPTION_END

;--------------------------------
;Uninstaller Section

Section "Uninstall"

  ;ADD YOUR OWN FILES HERE...

  RMDir /r "$INSTDIR"
  RMDir /r "$LOCALAPPDATA\Arelle"

  !insertmacro MUI_STARTMENU_GETFOLDER Application $StartMenuFolder
    
  Delete "$SMPROGRAMS\$StartMenuFolder\Uninstall.lnk"
  Delete "$SMPROGRAMS\$StartMenuFolder\*.*"
  RMDir "$SMPROGRAMS\$StartMenuFolder"

  DeleteRegKey HKLM "${ARELLE_UNINSTALL_KEY}"
  DeleteRegKey /ifempty HKLM "Software\Arelle"

SectionEnd
