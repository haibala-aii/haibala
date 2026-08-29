Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
root = fso.GetParentFolderName(dir)
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = root
sh.Run "pythonw.exe """ & dir & "\app.py""", 0, False
