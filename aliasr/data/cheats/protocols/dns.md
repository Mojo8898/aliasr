# DNS
#target/remote #os/linux #proto/dns #port/53

## Query records
```
dig any @<ip> <domain> +short
```

## Reverse lookup
```
dig -x @<ip> <domain> +short
```

## Zone transfer
```
dig axfr @<ip> <domain>
```
