# Reconnaissance
#target/remote #os/linux #cat/recon

## port scan all in one
```
mkdir -p nmap

naabu -host <ip> -p 1-10000 -duc -o 'nmap/<ip>_10k_tcp.out' -s s -source-ip <lhost> -i <interface|tun0> -nmap-cli 'nmap -sCV -oX nmap/<ip>_10k_tcp.xml' -Pn -ss -silent -rate <rate_limit|1000> -retries <retries|3>

nmap -Pn -n -sU -v -T4 --top-ports 200 -oA 'nmap/<ip>_200_udp' <ip>

naabu -host <ip> -p 10001-65535 -duc -o 'nmap/<ip>_remaining_tcp.out' -s s -source-ip <lhost> -i <interface|tun0> -nmap-cli 'nmap -sCV -oX nmap/<ip>_remaining_tcp.xml' -Pn -ss -silent -rate <rate_limit|1000> -retries <retries|3>
```

## fping
```
fping -asgq <cidr>
```

## host discovery all in one
```
fping -asgq <cidr>
sudo nmap -PO1 -n -v --top-ports 500 --exclude-port 9100 --open --min-rate 1000 <cidr>
sudo nmap -Pn -n --top-ports 500 --exclude-port 9100 --open --min-rate 1000 <cidr>
```

## nbtscan
```
nbtscan -r <cidr>
```
