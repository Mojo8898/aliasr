# Host Discovery
#target/remote #os/linux #cat/recon

## fping
```
fping -asgq <cidr>
```

## Host discovery all in one
```
fping -asgq <cidr>; sudo nmap -PO1 -n -v --top-ports 500 --exclude-port 9100 --open --min-rate 1000 <cidr>; sudo nmap -Pn -n --top-ports 500 --exclude-port 9100 --open --min-rate 1000 <cidr>
```

## nbtscan
```
nbtscan -r <cidr>
```

## Basic port scan
```
nmap -Pn -n -v --exclude-port 9100 --open --min-rate 1000 <ip>
```
