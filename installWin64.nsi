;Arelle Installer User Interface
;Adapted from Basic Example Script
;Written by Joost Verburg
;Tailored for Arelle 2011-04-28

;--------------------------------
;Include Modern UI

  !include "MUI2.nsh"

;--------------------------------
;General

  ;Name and file
  Name "Arelle"
  Icon arelle\images\arelle.ico
  UninstallIcon arelle\images\arelle.ico
  OutFile "dist\arelle-win-x64.exe"

  ;Default installation folder
  InstallDir "$PROGRAMFILES64\Arelle"
  
  ;Get installation folder from registry if available
  InstallDirRegKey HKLM "Software\Arelle" ""

  ;Request application privileges for Windows Vista
  RequestExecutionLevel none

;--------------------------------
;Variables

  Var StartMenuFolder

;--------------------------------
;Interface Settings

  !define MUI_ABORTWARNING

;--------------------------------
;Pages

  !insertmacro MUI_PAGE_LICENSE "License.txt"
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
  
  ;ADD YOUR OWN FILES HERE...
  File /r build\exe.win-amd64-3.2\*.*
  
  ;Store installation folder
  WriteRegStr HKLM "Software\Arelle" "" $INSTDIR
  ; Write the uninstall keys for Windows
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arelle" "DisplayName" "Arelle"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arelle" "Publisher" "arelle.org"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arelle" "RegOwner" "Mark V Systems Limited"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arelle" "URLInfoAbout" "http://arelle.org"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arelle" "DisplayIcon" '"$INSTDIR\images\arelle16x16and32x32.ico"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arelle" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arelle" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arelle" "NoRepair" 1
  
  ;Create uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  
  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
    
    ;Create shortcuts
    CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
    CreateShortCut "$SMPROGRAMS\$StartMenuFolder\Arelle.lnk" "$INSTDIR\arelle.exe"
    CreateShortCut "$SMPROGRAMS\$StartMenuFolder\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  
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

  Delete "$INSTDIR\Uninstall.exe"
  Delete "$INSTDIR\*.*"

  RMDir /r "$INSTDIR\config"
  RMDir /r "$INSTDIR\images"
  RMDir /r "$INSTDIR\tcl"
  RMDir /r "$INSTDIR\tk"
  RMDir "$INSTDIR"

  !insertmacro MUI_STARTMENU_GETFOLDER Application $StartMenuFolder
    
  Delete "$SMPROGRAMS\$StartMenuFolder\Uninstall.lnk"
  RMDir "$SMPROGRAMS\$StartMenuFolder"

  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arelle"
  DeleteRegKey /ifempty HKLM "Software\Arelle"

SectionEnd