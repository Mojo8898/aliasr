# Variations

Variations allow you to create placeholder parameters (such as for authentication) that invoke a separate menu before the build menu when selecting a command. In the variations menu, you can choose different predefined command snippets that are then used when returning to the build menu. See the following snippet from [variations.toml](../cheats/variations.toml):

```toml
[bloodyAD.auth]
Password = "-p '<password>'"
"NT hash" = "-p :<nt_hash>"
Kerberos = "-k"
```

This snippet is applied to the following example cheat for bloodyAD for example:

``````md
## Get writable
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> get writable
```
``````

The `<auth>` parameter invokes the variations menu when the cheat is selected, which contains the options defined by the associated variation definition.

In this example, the selection menu would include the following options:

- `Password`
- `NT hash`
- `Kerberos`

Selecting `Password`, for example, would then replace `<auth>` within the command and open the build menu with the following command to be built:

```md
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' -p '<password>' get writable
```

Variations are also titled using the following schema:

```
[<first_word>.<parameter_to_replace>]
```

You can create a variation that applies across all commands with the following schema:

```
[_.<parameter_to_replace>]
```

You can define custom variations in a `variations.toml` file, which is referenced and merged automatically in the same way as `config.toml`, at the same location (`~/.config/aliasr/variations.toml`).
