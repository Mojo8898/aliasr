# sqlmap
#target/remote #os/linux #cat/web

## Test GET request
```
sqlmap -u <url> -p <param> --batch
```

## Test POST request with cookie
```
sqlmap -u <url> --cookie '<cookie>' --data '<data>' -p <param> --batch
```

## Test request from burp
```
sqlmap -r <req_file> -p <param> --batch
```
