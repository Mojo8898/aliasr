# DNS
#target/remote #os/linux #proto/dns #port/53

## dig query
```
dig any @<ip> <domain> +short
```

## dig reverse ptr lookup
```
dig -x @<ip> <domain> +short
```

## dig zone transfer
```
dig axfr @<ip> <domain>
```
