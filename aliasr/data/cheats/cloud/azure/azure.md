# azure
#target/remote #os/linux #cat/cloud #cat/azure

## Authenticate with azure CLI
```
az login -u '<user>' -p <password> | jq .
```

## Azure session enum all in one
```
(az account list; az account tenant list --only-show-errors;az account subscription list --only-show-errors;az ad signed-in-user show;az ad signed-in-user list-owned-objects) | jq .
```

## AzureHound using creds
```
./azurehound list -u '<user>' -p <password> -t <tenant> -o <outfile>
```

## Run AzureHound using azure-cli session to auth
```
./azurehound list -j "$(az account get-access-token --resource https://graph.microsoft.com | jq -r .accessToken)" -t <tenant> -o <outfile>
```

## RoadRecon
```
roadrecon auth -u '<user>' -p <password> && roadrecon gather && roadrecon plugin policies && cat caps.html && roadrecon gui
```

## AzurePEASS
```
python3 AzurePEAS.py --username '<user>' --password <password>
```
