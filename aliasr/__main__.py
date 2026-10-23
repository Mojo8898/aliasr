import os
import argparse


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aliasr",
        description="aliasr - Modern TUI launcher for pentest commands",
    )
    p.add_argument(
        "-e",
        "--exec",
        dest="execute",
        action="store_true",
        help="Execute the command immediately",
    )

    sub = p.add_subparsers(dest="cmd")

    # ---------- Audit ----------

    audit = sub.add_parser(
        "audit",
        help="Audit cheatsheets and configs (no flag = brief summary of all)",
    )
    audit.add_argument("-c", "--cheats", action="store_true", help="Audit cheatsheets")
    audit.add_argument(
        "-r", "--references", action="store_true", help="Audit parameter references"
    )
    audit.add_argument(
        "-v", "--variations", action="store_true", help="Audit variations (variations.toml)"
    )
    audit.add_argument(
        "--config", action="store_true", help="Audit configuration (config.toml)"
    )
    audit.add_argument(
        "-a", "--all", action="store_true", help="Run every audit section in full"
    )
    audit.add_argument(
        "-l", "--list-all", action="store_true",
        help="With --cheats, list every individual cheat",
    )

    # ---------- Send ----------

    send = sub.add_parser("send", help="Modify how commands are sent")
    send_mx = send.add_mutually_exclusive_group()
    send_mx.add_argument("-c", "--copy", action="store_true", help="Copy to clipboard")
    send_mx.add_argument("-o", "--outfile", metavar="FILE", help="Write to file")
    send_mx.add_argument(
        "-p", "--pane", metavar="PANE", nargs="?", const="0", help="Send to tmux pane"
    )
    send_mx.add_argument(
        "-pp", "--previous-pane", action="store_true", help="Send to previous tmux pane"
    )

    # ---------- Scan ----------

    scan = sub.add_parser("scan", help="Auto-populate globals from a target IP")
    scan.add_argument(
        "ip",
        metavar="IP",
        help="Target IP address to scan"
    )

    # Authentication: these mirror NetExec's own flags and are passed straight
    # through to nxc, so any combination NetExec accepts is accepted here.
    scan.add_argument(
        "-u", "--user",
        metavar="USER",
        help="Username for authenticated scan"
    )
    scan.add_argument(
        "-p", "--password",
        metavar="PASSWORD",
        help="Password for authenticated scan"
    )
    scan.add_argument(
        "-H", "--hash",
        metavar="HASH",
        help="NT hash for authenticated scan"
    )
    scan.add_argument(
        "-k", "--kerberos",
        action="store_true",
        help="Use Kerberos auth (requests a TGT from the supplied creds, "
             "or uses the ccache when given alone)"
    )
    scan.add_argument(
        "--use-kcache",
        action="store_true",
        help="Use Kerberos auth from the ccache (KRB5CCNAME)"
    )

    # ---------- List ----------

    list_cmd = sub.add_parser("list", help="List globals or credentials")
    list_sub = list_cmd.add_subparsers(dest="list_cmd", required=True, help="What to list")
    list_sub.add_parser("globals", help="List all globals and their current values")
    list_sub.add_parser("creds", help="List all saved credentials")
    list_sub.add_parser("all", help="List both globals and credentials")

    # ---------- Clear ----------

    clear = sub.add_parser(
        "clear", help="Clear session data"
    )
    clear_sub = clear.add_subparsers(dest="clear_cmd", required=True)

    # Shared --yes for the destructive clears, which prompt for confirmation.
    yes_parent = argparse.ArgumentParser(add_help=False)
    yes_parent.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )

    clear_sub.add_parser(
        "cache", help="Clear cheats cache (rebuilds automatically when cheats change)"
    )
    clear_sub.add_parser("globals", help="Clear globals")
    clear_sub.add_parser("creds", parents=[yes_parent], help="Clear credentials")
    clear_sub.add_parser("hosts", parents=[yes_parent], help="Clear hosts")
    clear_sub.add_parser("all", parents=[yes_parent], help="Clear everything")

    p.set_defaults(copy=False, outfile=None, pane=None, previous_pane=False)
    return p


def _update_stale_config() -> None:
    """Before launching, if the in-use config.toml is missing options added in a
    newer aliasr, add those declarations (with their default values) to the file
    in place, preserving existing values. No prompt; once added it won't recur."""
    from aliasr.core.config import inject_missing_defaults, stale_config

    stale = stale_config()
    if not stale:
        return
    path, missing = stale

    print(f"Your config is missing {len(missing)} option(s) from a newer aliasr:")
    for key in missing[:15]:
        print(f"  - {key}")
    if len(missing) > 15:
        print(f"  ...and {len(missing) - 15} more")
    print(f"Config: {path}")
    try:
        inject_missing_defaults(path, missing)
        print("Your config has been updated with the new default(s).")
    except OSError as e:
        print(f"Could not update config: {e}")
    print()


def main() -> int:
    args = _parser().parse_args()

    if args.cmd == "clear":
        from aliasr.core.bootstrap import clear_flags, confirm_clear

        if not confirm_clear(args.clear_cmd, getattr(args, "yes", False)):
            print("Aborted.")
            return 1

        clear_cache = args.clear_cmd in ("cache", "all")
        clear_globals = args.clear_cmd in ("globals", "all")
        clear_creds = args.clear_cmd in ("creds", "all")
        clear_hosts = args.clear_cmd in ("hosts", "all")
        clear_flags(clear_cache, clear_globals, clear_creds, clear_hosts)
        return 0

    if args.cmd == "audit":
        from aliasr.audit import run_audit_cli

        return run_audit_cli(
            cheats=args.cheats,
            references=args.references,
            variations=args.variations,
            config=args.config,
            run_all=args.all,
            list_all=args.list_all,
        )

    if args.cmd == "list":
        from aliasr.core.list import run_list
        return run_list(args.list_cmd)

    if args.cmd == "scan":
        from aliasr.core.scan import run_scan_cli
        return run_scan_cli(
            args.ip,
            args.user,
            args.password,
            getattr(args, "hash", None),
            getattr(args, "kerberos", False),
            getattr(args, "use_kcache", False),
        )

    _update_stale_config()

    os.environ.setdefault("COLORTERM", "truecolor")

    from aliasr.core.bootstrap import launch_app

    app = launch_app(
        execute=args.execute,
        pane=args.pane,
        previous=args.previous_pane,
    )

    app.run()

    # ---------- Delivery ----------

    cmd = getattr(app, "pending_inject", None)
    if not cmd:
        return 0

    from aliasr.core.inject import inject

    return inject(
        cmd=cmd,
        copy=args.copy,
        outfile=args.outfile,
        using_tmux=app.in_tmux,
        execute=app.execute_cmd,
        pane_index=app.tmux_target_pane,
    )


if __name__ == "__main__":
    raise SystemExit(main())
