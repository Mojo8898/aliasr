# CorpCrack
#target/local #os/linux #cat/cracking #cat/bruteforce

## company pattern wordlist
```
corpcrack -s <company_short_name|ACME> -l "<company_long_name>" --patterns company -o <outfile|passwords.txt>
```

## full engagement run
```
corpcrack -s <company_short_name|ACME> -l "<company_long_name>" --year-start <year_start|2022> --year-end <year_end|2026> -o <outfile|passwords.txt>
```

## spray list (hand-picked patterns)
```
corpcrack -s <company_short_name|ACME> -l "<company_long_name>" --year-start <year_start|2024> --year-end <year_end|2026> --patterns <patterns|static,company,welcome_current,season_current,month_current,company_current> -o <outfile|passwords.txt>
```

- company_long_name
Acme Corporation
