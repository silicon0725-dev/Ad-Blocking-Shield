' Console-free launcher for the ad-block GUI.
' Pure ASCII on purpose: paths are resolved at runtime so this file is
' immune to ANSI/Unicode codepage issues on Chinese Windows.
' Picks the GUI exe from bin\ by exclusion (anything but mitmdump.exe);
' falls back to pythonw dev mode if bin\ is missing.
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)

exe = ""
If fso.FolderExists(dir & "\bin") Then
  For Each f In fso.GetFolder(dir & "\bin").Files
    If LCase(fso.GetExtensionName(f.Name)) = "exe" And LCase(f.Name) <> "mitmdump.exe" Then
      exe = f.Path
    End If
  Next
End If

If exe <> "" Then
  sh.Run """" & exe & """", 1, False
Else
  py = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python314\pythonw.exe"
  If fso.FileExists(py) Then sh.Run """" & py & """ """ & dir & "\gui\main.py""", 0, False
End If
