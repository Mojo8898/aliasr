"""Behavioral tests for the standalone `arun` wrapper (scripts/arun)."""

import os
import subprocess
from pathlib import Path

# Shipped as a wheel data-script (pyproject [tool.setuptools] script-files), so
# in the source tree it lives at the repo root, not inside the package.
ARUN = Path(__file__).resolve().parent.parent / "scripts" / "arun"


def _run(argv, env_extra=None, path_prepend=None):
    env = {k: v for k, v in os.environ.items() if k != "FAKETIME"}
    if env_extra:
        env.update(env_extra)
    if path_prepend:
        env["PATH"] = f"{path_prepend}{os.pathsep}{env.get('PATH', '')}"
    return subprocess.run(
        ["/bin/sh", str(ARUN), *argv], capture_output=True, text=True, env=env
    )


def test_arun_announces_and_runs_bare_without_skew():
    # AR_SKEW unset -> command runs directly. Banner on stderr, output on stdout.
    r = _run(["echo", "hi"])
    assert r.returncode == 0, r.stderr
    assert "=== echo hi ===" in r.stderr  # banner goes to stderr, not stdout
    assert "=== echo hi ===" not in r.stdout
    assert r.stdout.strip() == "hi"


def test_arun_banner_stays_out_of_a_pipe():
    """Regression: the banner must not pollute a step's stdout, or `... | jq`,
    `... > file` and `... | tee` would ingest it. Here a JSON producer piped to a
    strict consumer must see only the producer's stdout."""
    r = subprocess.run(
        ["/bin/sh", "-c", f"/bin/sh {ARUN} printf '{{\"k\":1}}' | cat"],
        capture_output=True,
        text=True,
        env={k: v for k, v in os.environ.items() if k != "FAKETIME"},
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout == '{"k":1}'  # only the command's stdout went down the pipe
    assert "===" in r.stderr  # banner still shown, on stderr


def test_arun_propagates_exit_status():
    # `exec` hands over the process, so `arun false` must fail (for &&/|| chains).
    r = _run(["false"])
    assert r.returncode != 0


def test_arun_runs_under_skewrun_when_ar_skew_set(tmp_path):
    stub = tmp_path / "skewrun"
    stub.write_text(
        '#!/bin/sh\necho "SKEW:$1"\nshift 2\nexec "$@"\n'
    )  # $1=target; drop target + '--'
    stub.chmod(0o755)

    r = _run(
        ["echo", "deep"], env_extra={"AR_SKEW": "10.9.8.7"}, path_prepend=str(tmp_path)
    )
    assert r.returncode == 0, r.stderr
    assert "SKEW:10.9.8.7" in r.stdout  # skewrun got the target
    assert "deep" in r.stdout  # and the wrapped command still ran


def test_arun_skips_skewrun_when_faketime_already_set(tmp_path):
    # Already inside a faketime'd shell: skewrun must NOT run, or skew doubles.
    stub = tmp_path / "skewrun"
    stub.write_text('#!/bin/sh\necho "SKEW-RAN"\nshift 2\nexec "$@"\n')
    stub.chmod(0o755)

    r = _run(
        ["echo", "deep"],
        env_extra={"AR_SKEW": "10.9.8.7", "FAKETIME": "-1h"},
        path_prepend=str(tmp_path),
    )
    assert r.returncode == 0, r.stderr
    assert "SKEW-RAN" not in r.stdout  # skewrun skipped despite AR_SKEW being set
    assert r.stdout.strip() == "deep"


def test_arun_chain_persists_cross_step_export(tmp_path):
    """The linchpin of the rework: because steps are emitted UNQUOTED, a step's
    trailing `&& export KRB5CCNAME=...` runs in the parent shell, so a *later*
    arun step (a child process, via skewrun) inherits it. Mirrors the AD
    all-in-one's getTGT -> ccache -> kerberos-auth flow."""
    (tmp_path / "arun").write_text(ARUN.read_text())
    (tmp_path / "skewrun").write_text(
        '#!/bin/sh\nshift 2\nexec "$@"\n'
    )  # drop target + '--'
    (tmp_path / "getTGT.py").write_text("#!/bin/sh\n:\n")
    (tmp_path / "bloodyAD").write_text('#!/bin/sh\necho "BLOODY:$KRB5CCNAME"\n')
    for name in ("arun", "skewrun", "getTGT.py", "bloodyAD"):
        (tmp_path / name).chmod(0o755)

    chain = (
        "export AR_SKEW=1.2.3.4 ; \\\n"
        "arun getTGT.py x && export KRB5CCNAME=/tmp/foo.ccache ; \\\n"
        "arun bloodyAD"
    )
    env = {**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"}
    env.pop("FAKETIME", None)
    r = subprocess.run(["bash", "-c", chain], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert "BLOODY:/tmp/foo.ccache" in r.stdout  # later step inherited the export
