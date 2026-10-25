# sqlmap
#target/remote #os/linux #cat/web

## sqlmap test get request
```
sqlmap -u '<url>' -p <param> --batch
```

## sqlmap test post request with cookie
```
sqlmap -u '<url>' --cookie '<cookie>' --data '<data>' -p <param> --batch
```

## sqlmap test request from burp
```
sqlmap -r <req_file> -p <param> --batch
```
