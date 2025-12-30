# openssl
#target/local #os/linux #cat/utils

## Dump info from .pem
```
openssl x509 -in <pem> -text -noout
```

## Create .pfx from .crt and .key
```
openssl pkcs12 -export -inkey <in_key> -in <in_crt> -out <out_pfx>
```
