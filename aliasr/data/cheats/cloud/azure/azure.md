# azure
#target/remote #os/linux #cat/cloud #cat/azure

## azure cli authenticate
```
az login -u '<user>' -p <password> | jq .
```

## azure session enum all in one
```
(az account list; az account tenant list --only-show-errors;az account subscription list --only-show-errors;az ad signed-in-user show;az ad signed-in-user list-owned-objects) | jq .
```

## azurehound
```
./azurehound list -u '<user>' -p <password> -t <tenant> -o <outfile>
```

## azurehound using azure-cli session
```
./azurehound list -j "$(az account get-access-token --resource https://graph.microsoft.com | jq -r .accessToken)" -t <tenant> -o <outfile>
```

## roadrecon
```
roadrecon auth -u '<user>' -p <password> && roadrecon gather && roadrecon plugin policies && cat caps.html && roadrecon gui
```

## azurepeass
```
python3 AzurePEAS.py --username '<user>' --password <password>
```
