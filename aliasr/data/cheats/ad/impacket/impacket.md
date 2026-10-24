# impacket
#target/remote #os/linux #cat/ad

## lookupsid
```
lookupsid.py <domain>/'<user>'<impacket_target_auth>
```

## Get computers
```
GetADComputers.py -resolveIP <domain>/'<user>'<impacket_auth> -dc-ip <dc_ip>
```

## netview (monitor sessions, requires admin)
```
netview.py <domain>/'<user>' -target <fqdn>
```

## smbserver
```
smbserver.py -smb2support <share|a> <path|.> -username <user|mojo> -password <password|'Password123!'>
```

## convert kirbi to ccache
```
echo '<base64_kirbi>' | base64 -d > <user>.kirbi && ticketConverter.py <user>.kirbi <user>.ccache && export KRB5CCNAME=$(pwd)/<user>.ccache
```
