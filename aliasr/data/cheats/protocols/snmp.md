# SNMP
#target/remote #os/linux #proto/snmp #port/161

## Brute force community strings
```
snmpbrute.py -t <ip> -f <wordlist|/usr/share/seclists/Discovery/SNMP/common-snmp-community-strings.txt>
```

## Enumerate public community string
```
snmpbulkwalk -Cr1000 -c <community_string|public> -v2c <ip> . > snmpwalk.out
```
