"""The official rules in a worker process, within a time limit (REQ-002-PRS-NF004,
REQ-002-PRS-NF005, ADR-010)."""

import _thread
import contextlib
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Generator, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import FrameType
from typing import Any

import pytest

from haflinger import (
    Finding,
    InvoiceReadError,
    InvoiceWriteError,
    _saxon,
    is_valid,
    read_invoice,
    validate,
    write_cii,
)
from haflinger.pdf import embed

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "tests/data/kosit-testsuite/instances/standard"
CII = SUITE / "01.01a-INVOICE_uncefact.xml"
UBL = SUITE / "01.01a-INVOICE_ubl.xml"
PDFA = next((ROOT / "tests/data/verapdf-corpus").rglob("*.pdf"))
EN16931 = "urn:cen.eu:en16931:2017"
INVOICE = replace(read_invoice(CII.read_bytes()).invoice, specification_id=EN16931)
VARIABLE = "HAFLINGER_RULES_TIMEOUT"


def slow_invoice() -> bytes:
    """KoSIT case 01.20a in UBL with 16,000 distinct `cbc:PaymentID`: CEN's `UBL-SR-44` compares
    each with every one before it, about 5 s (REQ-002's assumptions)."""
    text = (SUITE / "01.20a-INVOICE_ubl.xml").read_text(encoding="utf-8")
    one = "<cbc:PaymentID>1234567890</cbc:PaymentID>"
    assert text.count(one) == 1
    return text.replace(
        one, "".join(f"<cbc:PaymentID>{i}</cbc:PaymentID>" for i in range(16000))
    ).encode()


SLOW = slow_invoice()


@pytest.fixture(autouse=True)
def no_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(VARIABLE, raising=False)


# REQ-002-PRS-NF004: the time limit


def test_validate_gives_up_after_its_timeout() -> None:
    start = time.monotonic()
    with pytest.raises(InvoiceReadError, match=r"took longer than 0\.5 s"):
        validate(SLOW, timeout=0.5)
    assert time.monotonic() - start < 1.5
    assert is_valid(validate(CII.read_bytes()))


def test_write_cii_gives_up_after_its_timeout() -> None:
    _saxon.clear_caches()  # starting the worker and compiling the rules count against the limit
    with pytest.raises(InvoiceWriteError, match=r"took longer than 0\.05 s") as error:
        write_cii(INVOICE, timeout=0.05)
    assert error.value.document is not None
    assert write_cii(INVOICE)


def test_embed_gives_up_after_its_timeout() -> None:
    xml = write_cii(INVOICE)
    _saxon.clear_caches()
    with pytest.raises(InvoiceWriteError, match=r"took longer than 0\.05 s"):
        embed(PDFA.read_bytes(), xml, timeout=0.05)
    assert embed(PDFA.read_bytes(), xml)


def test_the_variable_sets_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE, "0.5")
    start = time.monotonic()
    with pytest.raises(InvoiceReadError, match=r"took longer than 0\.5 s"):
        validate(SLOW)
    assert time.monotonic() - start < 1.5


def test_an_explicit_timeout_overrides_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE, "60")
    with pytest.raises(InvoiceReadError, match=r"took longer than 0\.5 s"):
        validate(SLOW, timeout=0.5)
    monkeypatch.setenv(VARIABLE, "abc")
    assert is_valid(validate(CII.read_bytes(), timeout=60))


INVALID = [0, -1, float("nan"), float("inf"), 1e10, 10**400, 31_536_000.5, True, "60"]


@pytest.mark.parametrize("timeout", INVALID, ids=repr)
def test_validate_refuses_an_invalid_timeout(timeout: Any) -> None:
    with pytest.raises(InvoiceReadError, match="timeout"):
        validate(CII.read_bytes(), timeout=timeout)


@pytest.mark.parametrize("timeout", INVALID, ids=repr)
def test_write_cii_refuses_an_invalid_timeout_before_writing(timeout: Any) -> None:
    with pytest.raises(InvoiceWriteError, match="timeout") as error:
        write_cii(INVOICE, timeout=timeout)
    assert error.value.document is None
    assert error.value.findings == ()


@pytest.mark.parametrize("timeout", INVALID, ids=repr)
def test_embed_refuses_an_invalid_timeout(timeout: Any) -> None:
    with pytest.raises(InvoiceWriteError, match="timeout"):
        embed(PDFA.read_bytes(), write_cii(INVOICE), timeout=timeout)


@pytest.mark.parametrize("value", ["abc", "0", "-1", "nan", "inf", "1e10", "1" + "0" * 400])
def test_an_invalid_variable_is_refused(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE, value)
    with pytest.raises(InvoiceReadError, match=VARIABLE):
        validate(CII.read_bytes())
    with pytest.raises(InvoiceWriteError, match=VARIABLE):
        write_cii(INVOICE)


def test_a_call_waiting_behind_a_slow_one_gives_up_alone() -> None:
    """The wait for another thread's call counts against the limit; the other call goes on."""
    with ThreadPoolExecutor(1) as pool:
        slow = pool.submit(validate, SLOW, timeout=60)
        time.sleep(1.0)  # the slow call now holds the worker
        start = time.monotonic()
        with pytest.raises(InvoiceReadError, match=r"took longer than 0\.5 s"):
            validate(CII.read_bytes(), timeout=0.5)
        assert time.monotonic() - start < 1.5
        assert "UBL-SR-44" in {finding.rule for finding in slow.result()}


# REQ-002-PRS-NF005: the worker process


def test_the_caller_never_imports_saxon() -> None:
    script = f"""
import sys
from dataclasses import replace
import haflinger
from haflinger.pdf import embed
data = open({str(CII)!r}, "rb").read()
haflinger.validate(data)
invoice = replace(haflinger.read_invoice(data).invoice, specification_id={EN16931!r})
embed(open({str(PDFA)!r}, "rb").read(), haflinger.write_cii(invoice))
assert "saxonche" not in sys.modules, "saxonche loaded"
"""
    subprocess.run([sys.executable, "-c", script], check=True)  # noqa: S603


def test_a_worker_killed_between_calls_is_replaced() -> None:
    validate(CII.read_bytes())
    pid = _saxon.worker_pid()
    assert pid is not None
    os.kill(pid, signal.SIGKILL)
    deadline = time.monotonic() + 5
    while not _ended(pid) and time.monotonic() < deadline:
        time.sleep(0.01)  # until the kill has taken effect, as before a later call
    assert is_valid(validate(CII.read_bytes()))
    assert _saxon.worker_pid() not in (None, pid)


def _ended(pid: int) -> bool:
    """Whether a child process has ended, with all its threads, so that waiting for it returns
    at once; it is left for its parent to wait for. Its main thread shows as a zombie in `/proc`
    before its other threads have ended, and until then `Popen.poll` still finds it running."""
    try:
        return os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None
    except ChildProcessError:  # already waited for
        return True


def test_a_worker_killed_during_a_call_is_reported() -> None:
    validate(CII.read_bytes())
    pid = _saxon.worker_pid()
    assert pid is not None
    killer = threading.Timer(1.0, os.kill, (pid, signal.SIGKILL))
    killer.start()
    try:
        with pytest.raises(InvoiceReadError, match=r"worker .*died"):
            validate(SLOW, timeout=60)
    finally:
        killer.cancel()
    assert is_valid(validate(CII.read_bytes()))


def test_a_forked_child_starts_its_own_worker(tmp_path: Path) -> None:
    """Also when another thread of the parent is in a call at the fork, which holds the lock."""
    slow = tmp_path / "slow.xml"
    slow.write_bytes(SLOW)
    script = f"""
import os, threading, time, warnings
warnings.simplefilter("ignore", DeprecationWarning)
from haflinger import validate, _saxon
data = open({str(CII)!r}, "rb").read()
slow = open({str(slow)!r}, "rb").read()


def child(expected, parent):
    pid = os.fork()
    if pid == 0:
        ok = validate(data, timeout=30) == expected and _saxon.worker_pid() != parent
        os._exit(0 if ok else 1)
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0, "the child failed"


expected = validate(data)
parent = _saxon.worker_pid()
child(expected, parent)
results = []
busy = threading.Thread(target=lambda: results.append(validate(slow, timeout=60)))
busy.start()
time.sleep(1.0)
child(expected, parent)
busy.join()
assert results and _saxon.worker_pid() == parent, "the parent's call or worker was disturbed"
"""
    subprocess.run([sys.executable, "-c", script], check=True, timeout=120)  # noqa: S603


def test_threads_each_get_their_own_findings() -> None:
    files = sorted(SUITE.glob("*.xml"))[:8]
    expected = [validate(path.read_bytes()) for path in files]
    with ThreadPoolExecutor(8) as pool:
        assert list(pool.map(validate, [path.read_bytes() for path in files])) == expected


MESSAGE = """<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="3.0">
  <xsl:template match="/"><xsl:message>a message on stderr</xsl:message><r/></xsl:template>
</xsl:stylesheet>"""


@pytest.fixture
def artefacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A stylesheet of the test's own in place of the vendored artefacts."""
    (tmp_path / "message.xsl").write_text(MESSAGE, encoding="utf-8")
    monkeypatch.setattr(_saxon, "ARTEFACTS", tmp_path)
    _saxon.clear_caches()
    yield tmp_path
    monkeypatch.undo()
    _saxon.clear_caches()


def test_what_saxon_prints_goes_to_logging(
    artefacts: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="haflinger")
    (result,) = _saxon.transform(b"<x/>", "message.xsl", timeout=10)
    assert result.endswith(b"<r/>")
    deadline = time.monotonic() + 5
    while "a message on stderr" not in caplog.text and time.monotonic() < deadline:
        time.sleep(0.05)
    assert "a message on stderr" in caplog.text
    assert all(record.name.startswith("haflinger") for record in caplog.records)


def test_a_year_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    assert is_valid(validate(CII.read_bytes(), timeout=31_536_000))
    monkeypatch.setenv(VARIABLE, "31536000")
    assert is_valid(validate(CII.read_bytes()))


class _InterruptedError(Exception):
    pass


@pytest.mark.timeout(method="thread")  # its own SIGALRM
def test_a_call_ended_by_a_signal_leaves_no_reply_behind() -> None:
    """As an RQ job timeout does, with SIGALRM: the next call gets its own findings."""
    expected = validate(CII.read_bytes())
    with _interrupted_after(1.0), pytest.raises(_InterruptedError):
        validate(SLOW, timeout=60)
    time.sleep(5)  # long enough for a worker left running to write its reply
    assert validate(CII.read_bytes()) == expected


@pytest.mark.timeout(method="thread")  # its own SIGALRM
def test_a_slow_call_ended_by_a_signal_doesnt_hold_up_the_next() -> None:
    """Its rules would run about 4 s more; the next call doesn't wait for them."""
    expected = validate(CII.read_bytes())
    with _interrupted_after(1.0), pytest.raises(_InterruptedError):
        validate(SLOW, timeout=60)
    start = time.monotonic()
    assert validate(CII.read_bytes(), timeout=2) == expected
    assert time.monotonic() - start < 2


@contextlib.contextmanager
def _interrupted_after(seconds: float) -> Generator[None]:
    """`_InterruptedError` raised by a signal handler after `seconds`, as RQ's job timeout."""

    def interrupt(signum: int, frame: object) -> None:
        raise _InterruptedError

    previous = signal.signal(signal.SIGALRM, interrupt)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


BROKEN = """<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="3.0">
  <xsl:template match="/"><xsl:value-of select="no-such-function()"/></xsl:template>
</xsl:stylesheet>"""


def test_a_stylesheet_that_doesnt_compile_is_no_finding(artefacts: Path) -> None:
    (artefacts / "broken.xsl").write_text(BROKEN, encoding="utf-8")
    for stylesheet in ("broken.xsl", "missing.xsl"):
        with pytest.raises(_saxon.WorkerError, match="can't be compiled") as error:
            _saxon.transform(b"<x/>", stylesheet, timeout=10)
        assert not isinstance(error.value, _saxon.TransformError)
    (result,) = _saxon.transform(b"<x/>", "message.xsl", timeout=10)
    assert result.endswith(b"<r/>")


def test_a_worker_that_cant_start_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _saxon.clear_caches()

    def refuse(*args: object, **kwargs: object) -> None:
        raise OSError(24, "Too many open files")

    monkeypatch.setattr(subprocess, "Popen", refuse)
    with pytest.raises(InvoiceReadError, match="can't be started"):
        validate(CII.read_bytes())
    with pytest.raises(InvoiceWriteError, match="can't be started") as error:
        write_cii(INVOICE)
    assert error.value.document is not None
    monkeypatch.undo()
    monkeypatch.setattr(sys, "executable", "")
    with pytest.raises(InvoiceReadError, match="can't be started"):
        validate(CII.read_bytes())


def test_a_call_past_its_deadline_before_sending_leaves_the_worker() -> None:
    validate(CII.read_bytes())
    pid = _saxon.worker_pid()
    with pytest.raises(_saxon.WorkerError, match="took longer"):
        _saxon.transform(CII.read_bytes(), "x.xsl", timeout=0.5, started=time.monotonic() - 1)
    assert _saxon.worker_pid() == pid


def test_validation_works_with_many_files_open() -> None:
    """Beyond the 1,024 file descriptors that select() handles."""
    import resource

    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft < 2048 and (hard == resource.RLIM_INFINITY or hard >= 2048):
        resource.setrlimit(resource.RLIMIT_NOFILE, (2048, hard))
    opened = [os.open(os.devnull, os.O_RDONLY) for _ in range(1100)]
    try:
        _saxon.clear_caches()  # the new worker's pipes get descriptors above 1,024
        assert is_valid(validate(CII.read_bytes()))
    finally:
        for descriptor in opened:
            os.close(descriptor)
        _saxon.clear_caches()  # no later test inherits the worker's high descriptors
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))


def _copy_of_haflinger(tmp_path: Path) -> Path:
    """A copy of Haflinger's package without its bytecode cache, for a caller's import path."""
    import shutil

    copy = tmp_path / "path" / "haflinger"
    shutil.copytree(ROOT / "src/haflinger", copy, ignore=shutil.ignore_patterns("__pycache__"))
    return copy


def test_the_worker_uses_the_callers_haflinger(tmp_path: Path) -> None:
    """A copy of Haflinger found on the caller's own import path, as with PYTHONPATH: the worker
    runs that copy, not the one installed in the environment."""
    copy = _copy_of_haflinger(tmp_path)
    worker = copy / "_worker.py"
    text = worker.read_text(encoding="utf-8")
    marker = "def main() -> None:\n"
    assert text.count(marker) == 1
    worker.write_text(
        text.replace(marker, marker + "    print('worker from', __file__, file=sys.stderr)\n"),
        encoding="utf-8",
    )
    script = f"""
import logging, sys
logging.basicConfig(level=logging.WARNING)
sys.path.insert(0, {str(copy.parent)!r})
import haflinger
assert haflinger.__file__.startswith({str(copy)!r}), haflinger.__file__
haflinger.validate(open({str(CII)!r}, "rb").read())
"""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script], check=True, capture_output=True, text=True, timeout=60
    )
    assert f"worker from {copy / '_worker.py'}" in result.stderr


def _validate_in(copy: Path, *flags: str) -> None:
    """Validates in a fresh interpreter started with `flags` that imports Haflinger from `copy`."""
    script = f"""
import sys
sys.path.insert(0, {str(copy.parent)!r})
import haflinger
haflinger.validate(open({str(CII)!r}, "rb").read())
"""
    subprocess.run([sys.executable, *flags, "-c", script], check=True, timeout=60)  # noqa: S603


def test_the_worker_writes_no_bytecode_where_the_caller_writes_none(tmp_path: Path) -> None:
    copy = _copy_of_haflinger(tmp_path)
    _validate_in(copy, "-B")
    assert not list(copy.rglob("__pycache__"))


def test_the_worker_writes_bytecode_where_the_caller_does(tmp_path: Path) -> None:
    copy = _copy_of_haflinger(tmp_path)
    prefix = tmp_path / "pycache"
    _validate_in(copy, "-X", f"pycache_prefix={prefix}")
    assert not list(copy.rglob("__pycache__"))
    assert list(prefix.rglob("_worker.*.pyc")), "the worker's bytecode isn't under the prefix"


def test_haflinger_imports_without_fork_handlers() -> None:
    """As on Windows, which has no os.register_at_fork: reading still works."""
    script = f"""
import os
del os.register_at_fork
import haflinger
haflinger.read_invoice(open({str(CII)!r}, "rb").read())
"""
    subprocess.run([sys.executable, "-c", script], check=True, timeout=60)  # noqa: S603


def test_an_exception_at_any_step_leaves_the_worker_in_step() -> None:
    """A signal handler's exception, as RQ's job timeout raises, lands between any two bytecodes
    of the calling thread. Raised at each bytecode of `_saxon` and of the XML Schema check,
    `_xsd`, in turn: each next call gets its own findings within its time limit, so no reply was
    left behind and no lock held."""
    data = CII.read_bytes()
    expected = validate(data)
    steps = _steps_of_a_call(data, raise_at=None)
    assert steps > 50
    for step in range(1, steps + 1):
        with contextlib.suppress(_InterruptedError):
            _steps_of_a_call(data, raise_at=step)
        assert _within(10, lambda: validate(data, timeout=5)) == expected, f"at step {step}"


def test_an_exception_while_the_helper_starts_reaches_the_caller() -> None:
    """Raised at each step of a process's first call up to its request, `threading`'s code
    included: the exception reaches the caller as it is, no lock of `threading` is left held,
    which would hang the next thread's start, and the next call gets its findings."""
    script = f"""
import sys, threading
from haflinger import _saxon, validate


class Interrupted(Exception):
    pass


STARTING = ("_current_helper", "__init__")
data = open({str(CII)!r}, "rb").read()
expected = validate(data)


def first_call(raise_at):
    _saxon._helper = None
    steps = 0

    def trace(frame, event, arg):
        nonlocal steps
        module = frame.f_globals.get("__name__")
        if module != "threading" and not (
            module == "haflinger._saxon" and frame.f_code.co_name in STARTING
        ):
            return None
        frame.f_trace_opcodes = True
        if event == "opcode":
            steps += 1
            if steps == raise_at:
                raise Interrupted
        return trace

    sys.settrace(trace)
    try:
        validate(data)
    finally:
        sys.settrace(None)
    return steps


steps = first_call(None)
assert steps > 10, steps
for step in range(1, steps + 1):
    try:
        first_call(step)
    except Interrupted:
        pass
    else:
        raise AssertionError(f"nothing raised at step {{step}}")
    thread = threading.Thread(target=lambda: None)
    thread.start()
    thread.join()
assert validate(data) == expected
"""
    subprocess.run([sys.executable, "-c", script], check=True, timeout=120)  # noqa: S603


def test_a_request_left_with_an_ended_helper_goes_to_the_current_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two threads that start a helper at once each get their own, and the one not kept ends
    when it is idle; a thread held up longer than that hands its request to an ended helper."""
    expected = validate(CII.read_bytes())
    current = _saxon._current_helper()  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(_saxon, "_helper", None)
    ended = _saxon._current_helper()  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(_saxon, "_helper", current)
    time.sleep(3 * _saxon._IDLE)  # pyright: ignore[reportPrivateUsage]
    handed = iter([ended])
    real = _saxon._current_helper  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(_saxon, "_current_helper", lambda: next(handed, None) or real())
    assert validate(CII.read_bytes(), timeout=5) == expected


def test_a_child_forked_while_the_worker_starts_holds_none_of_its_pipes() -> None:
    """The child would keep the worker's stdin open, and the worker running, after the parent
    has ended."""
    script = f"""
import os, subprocess, threading, time, warnings
warnings.simplefilter("ignore", DeprecationWarning)
from haflinger import _saxon, validate

data = open({str(CII)!r}, "rb").read()
started = threading.Event()


class SlowPopen(subprocess.Popen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        started.set()
        time.sleep(1)  # a fork comes while the worker is being started


subprocess.Popen = SlowPopen
caller = threading.Thread(target=lambda: validate(data))
caller.start()
started.wait()
read, write = os.pipe()
pid = os.fork()
if pid == 0:
    os.close(read)
    # /dev/fd lists the open descriptors on Linux and on macOS, which has no /proc.
    os.write(write, " ".join(os.listdir("/dev/fd")).encode())
    os._exit(0)
os.close(write)
held = {{int(fd) for fd in os.read(read, 65536).split()}}
_, status = os.waitpid(pid, 0)
assert os.waitstatus_to_exitcode(status) == 0, "the child failed"
assert held, "the child reported no descriptors"
caller.join()
worker = _saxon._helper.worker
pipes = {{worker.stdin.fileno(), worker.stdout.fileno(), worker.stderr.fileno()}}
assert not held & pipes, f"the child held {{sorted(held & pipes)}} of {{sorted(pipes)}}"
"""
    subprocess.run([sys.executable, "-c", script], check=True, timeout=60)  # noqa: S603


def _within(seconds: float, call: Callable[[], Sequence[Finding]]) -> Sequence[Finding] | None:
    """`call`'s result, or None where it hasn't returned within `seconds`, as when it waits for
    a lock that was left held."""
    results: list[Sequence[Finding]] = []
    thread = threading.Thread(target=lambda: results.append(call()), daemon=True)
    thread.start()
    thread.join(seconds)
    return results[0] if results else None


def _steps_of_a_call(data: bytes, raise_at: int | None) -> int:
    """Validate `data` with `_InterruptedError` raised at bytecode `raise_at` of the code of
    `_saxon` and `_xsd` in this thread; the number of their bytecodes run."""
    steps = 0

    def trace(frame: FrameType, event: str, arg: object) -> Any:
        nonlocal steps
        if frame.f_globals.get("__name__") not in ("haflinger._saxon", "haflinger._xsd"):
            return None
        frame.f_trace_opcodes = True
        if event == "opcode":
            steps += 1
            if steps == raise_at:
                raise _InterruptedError
        return trace

    sys.settrace(trace)
    try:
        validate(data)
    finally:
        sys.settrace(None)
    return steps


def test_a_worker_killed_while_taking_a_request_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Not sent again to a new worker: the request may be what killed it."""
    validate(CII.read_bytes())
    write = _saxon._write  # pyright: ignore[reportPrivateUsage]
    killed: list[int] = []

    def kill_halfway(descriptor: int, data: bytes, request: _saxon._Request) -> int:  # pyright: ignore[reportPrivateUsage]
        if killed:
            return write(descriptor, data, request)
        pid = _saxon.worker_pid()
        assert pid is not None
        written = write(descriptor, data[:100_000], request)
        os.kill(pid, signal.SIGKILL)
        killed.append(pid)
        while not _ended(pid):
            time.sleep(0.01)
        return written + write(descriptor, data[written:], request)

    monkeypatch.setattr(_saxon, "_write", kill_halfway)
    with pytest.raises(InvoiceReadError, match=r"worker .*died"):
        validate(SLOW, timeout=30)
    monkeypatch.undo()
    assert is_valid(validate(CII.read_bytes()))


def test_a_thread_that_cant_start_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The helper, and the thread that reads the worker's stderr."""

    def refuse(*args: object) -> None:
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(_saxon, "_helper", None)
    monkeypatch.setattr(_thread, "start_new_thread", refuse)
    with pytest.raises(InvoiceReadError, match="can't be started"):
        validate(CII.read_bytes())
    monkeypatch.undo()
    _saxon.clear_caches()
    monkeypatch.setattr(threading.Thread, "start", refuse)
    with pytest.raises(InvoiceReadError, match="can't be started"):
        validate(CII.read_bytes())
    monkeypatch.undo()
    assert is_valid(validate(CII.read_bytes()))


def test_an_import_path_entry_that_isnt_text_is_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "path", [*sys.path, None])
    _saxon.clear_caches()
    assert is_valid(validate(CII.read_bytes()))
