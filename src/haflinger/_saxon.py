"""Running official stylesheets with Saxon, unchanged (ADR-006), in a worker process (ADR-010).

The calling process never imports `saxonche`: a worker, a new interpreter started on first use
and kept, compiles and runs the stylesheets, and only text passes between them
(REQ-002-PRS-NF005). Each call has a time limit, after which the worker is killed
(REQ-002-PRS-NF004).

Only a helper thread of Haflinger's own talks to the worker. A call hands it a request on a
queue and waits for the reply on another, both implemented in C. Python runs signal handlers
only in the main thread, so an exception that a handler raises in a caller, such as RQ's job
timeout, ends that caller's wait but never the exchange with the worker, and no lock is left
held: the helper finishes the exchange, and the worker stays in step. The caller marks its
request abandoned, and the helper skips it or kills the worker running it, so that no later call
waits for rules whose reply nobody takes.
"""

import _thread
import logging
import math
import os
import reprlib
import select
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from queue import Empty, SimpleQueue
from typing import IO, cast

from haflinger._frames import LENGTH, frames
from haflinger._xml import decode
from haflinger.errors import InvoiceReadError

ARTEFACTS = Path(__file__).parent / "artefacts"
VARIABLE = "HAFLINGER_RULES_TIMEOUT"
DEFAULT_TIMEOUT = 60.0
MAX_TIMEOUT = 31_536_000.0  # a year; the platform's waits overflow far beyond it
_LOGGER = logging.getLogger("haflinger")
# The worker's import path is the caller's, so that it imports the same Haflinger and saxonche;
# -E keeps the PYTHON* variables out, -P the working directory (ADR-010).
_BOOT = "import sys; sys.path[:] = sys.argv[2:]; from haflinger._worker import main; main()"
_CHUNK = 1 << 20
_IDLE = 1.0  # how often an idle helper checks whether it is still the current one
_SLICE = 0.1  # how often a helper in an exchange, or a call waiting, checks on the other


class TransformError(InvoiceReadError):
    """Saxon failed on the document, which `validation` reports as `HAFL-RULES`."""


class WorkerError(InvoiceReadError):
    """No verdict on the document: the rules didn't end within the time limit, the worker
    running them died or couldn't be started, or a stylesheet couldn't be compiled."""


def time_limit(value: object = None) -> float:
    """The time limit of a call in seconds (REQ-002-PRS-NF004): `value`, or where it is None the
    variable `HAFLINGER_RULES_TIMEOUT`, read on each call, or 60 s."""
    if value is None:
        text = os.environ.get(VARIABLE)
        if text is None:
            return DEFAULT_TIMEOUT
        try:
            seconds = float(text)
        except ValueError:
            seconds = math.nan
        if not 0 < seconds <= MAX_TIMEOUT:
            raise InvoiceReadError(
                f"{VARIABLE} must be a number of seconds greater than 0 and at most"
                f" {MAX_TIMEOUT:,.0f} (a year), not {reprlib.repr(text)}"
            )
        return seconds
    # Comparing, unlike converting to float, works for any int, and is False for nan.
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not 0 < value <= MAX_TIMEOUT
    ):
        raise InvoiceReadError(
            "the timeout must be a number of seconds greater than 0 and at most"
            f" {MAX_TIMEOUT:,.0f} (a year), not {reprlib.repr(value)}"
        )
    return float(value)


def _cant_start(reason: object) -> WorkerError:
    return WorkerError(f"the worker for the official rules can't be started: {reason}")


def _too_long(limit: float) -> WorkerError:
    return WorkerError(f"the official rules took longer than {limit:g} s")


class _OutOfStepError(Exception):
    """A reply that answers another request."""


class _Worker:
    """A worker process. What it writes to stderr goes to logging; the lines of the current
    call are kept for the report of its death."""

    def __init__(self) -> None:
        if not sys.executable:
            raise _cant_start("Python doesn't know its own interpreter (sys.executable is empty)")
        flags = ["-E", "-P", *(["-s"] if sys.flags.no_user_site else [])]
        # Entries that aren't text, which import ignores, may be in it too.
        path = [entry for entry in cast(list[object], sys.path) if isinstance(entry, str) and entry]
        with _starting:  # a fork waits until the worker is in `_workers`
            try:
                self.process = subprocess.Popen(  # noqa: S603 - this interpreter, Haflinger's
                    [sys.executable, *flags, "-c", _BOOT, str(ARTEFACTS), *path],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0,
                )
            except (OSError, ValueError) as error:
                raise _cant_start(error) from None
            _workers.add(self)
        # Popen sets all three, as each is a pipe; unbuffered, so that no buffer's lock can be
        # held by another thread when the process forks.
        self.stdin = cast(IO[bytes], self.process.stdin)
        self.stdout = cast(IO[bytes], self.process.stdout)
        self.stderr = cast(IO[bytes], self.process.stderr)
        os.set_blocking(self.stdin.fileno(), False)
        self.said: deque[str] = deque(maxlen=50)
        self.reader = threading.Thread(target=self._log, name="haflinger-worker-stderr")
        self.reader.daemon = True
        try:
            self.reader.start()
        except RuntimeError as error:
            self.process.kill()
            self.process.wait()
            for stream in (self.stdin, self.stdout, self.stderr):
                stream.close()
            _workers.discard(self)
            raise _cant_start(error) from None

    def _log(self) -> None:
        """Log each line the worker writes to stderr, until it ends."""
        descriptor = self.stderr.fileno()
        pending = b""
        while chunk := os.read(descriptor, 65536):
            *lines, pending = (pending + chunk).split(b"\n")
            for line in lines:
                self._said(line)
        if pending:
            self._said(pending)
        self.stderr.close()

    def _said(self, line: bytes) -> None:
        text = line.decode(errors="replace").rstrip()
        self.said.append(text)
        _LOGGER.warning("Saxon's worker %d: %s", self.process.pid, text)

    def exchange(self, number: bytes, message: bytes, request: _Request) -> list[bytes] | None:
        """Send `message`, request `number`, and read its reply of `request.count` outputs; None
        when the request's deadline passes first or its caller has abandoned it. Raises
        `BrokenPipeError` or `EOFError` when the worker has ended, `_OutOfStepError` when the
        reply answers another request, `TransformError` when Saxon failed on the document, and
        `WorkerError` when a stylesheet doesn't compile."""
        self.said = deque(maxlen=50)  # what the worker wrote before is logged, not reported
        if _write(self.stdin.fileno(), message, request) < len(message):
            return None
        descriptor = self.stdout.fileno()
        answered = _read_frame(descriptor, request)
        if answered is None:
            return None
        if answered != number:
            raise _OutOfStepError
        status = _read_frame(descriptor, request)
        if status is None:
            return None
        if status in (b"error", b"broken"):
            said = _read_frame(descriptor, request)
            if said is None:
                return None
            text = said.decode(errors="replace")
            if status == b"broken":
                raise WorkerError(
                    "a stylesheet of the official rules can't be compiled; Haflinger's"
                    f" installation may be incomplete: {text}"
                )
            raise TransformError(f"Saxon can't process the input: {text}")
        outputs: list[bytes] = []
        for _ in range(request.count):
            output = _read_frame(descriptor, request)
            if output is None:
                return None
            outputs.append(output)
        return outputs

    def died(self, how: str = "died") -> WorkerError:
        """End the worker; the error for one that ended during a call, or fell out of step,
        with what it wrote to stderr during the call."""
        self.stop(kill=True)
        said = "; ".join(self.said.copy())
        code = self.process.returncode
        return WorkerError(
            f"the worker running the official rules {how}"
            + (f" (exit code {code})" if code is not None else "")
            + (f": {said}" if said else "")
        )

    def stop(self, *, kill: bool) -> None:
        """End the worker, within a few seconds at most, and close this side of its pipes; the
        reader closes stderr once the worker has ended."""
        if kill:
            self.process.kill()
        elif not self.stdin.closed:
            self.stdin.close()
        try:
            self.process.wait(timeout=1 if kill else 5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                _LOGGER.warning("Saxon's worker %d doesn't end", self.process.pid)
        self.reader.join(timeout=1)
        self.stdin.close()
        self.stdout.close()
        _workers.discard(self)

    def forget(self) -> None:
        """Drop a worker inherited through a fork: close this process's copies of its pipes
        and leave the worker to the parent."""
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream is not None:
                stream.close()
        self.process.returncode = 0  # not this process's child to wait for


# Every worker of this process, from its start until it has been stopped, also one that no
# helper holds yet or any more: a forked child closes its copies of their pipes (`_after_fork`).
# Only the helper threads start workers, holding `_starting`, which a fork waits for.
_workers: set[_Worker] = set()
_starting = threading.RLock()


def _ready(descriptor: int, events: int, request: _Request) -> bool:
    """Whether `descriptor` is ready before the request's deadline and while its caller waits
    for it. `poll`, unlike `select`, takes any descriptor, also beyond 1,023."""
    poller = select.poll()
    poller.register(descriptor, events)
    while not request.abandoned and (left := request.deadline - time.monotonic()) > 0:
        if poller.poll(math.ceil(min(left, _SLICE) * 1000)):
            return True
    return False


def _write(descriptor: int, data: bytes, request: _Request) -> int:
    """Write as much of `data` as `_ready` allows; the number of bytes written. Raises
    `BrokenPipeError` when the worker has ended."""
    view = memoryview(data)
    written = 0
    while written < len(data) and _ready(descriptor, select.POLLOUT, request):
        try:
            written += os.write(descriptor, view[written : written + _CHUNK])
        except BlockingIOError:
            continue
    return written


def _read_frame(descriptor: int, request: _Request) -> bytes | None:
    """The next frame; None where `_ready` gives up first. Raises `EOFError` when the worker
    has ended."""
    header = _read_exactly(descriptor, LENGTH.size, request)
    if header is None:
        return None
    (length,) = LENGTH.unpack(header)
    return _read_exactly(descriptor, length, request)


def _read_exactly(descriptor: int, size: int, request: _Request) -> bytes | None:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        if not _ready(descriptor, select.POLLIN, request):
            return None
        chunk = os.read(descriptor, min(remaining, _CHUNK))
        if not chunk:
            raise EOFError
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class _Request:
    """A call's request, and the queue its reply comes on: the outputs or the exception. The
    helper marks it taken; its caller, where it stops waiting, abandoned."""

    def __init__(
        self,
        names: bytes,
        text: bytes,
        count: int,
        limit: float,
        deadline: float,
        *,
        stop: bool = False,
    ) -> None:
        self.stop = stop  # stop the worker instead: `clear_caches`
        self.names = names
        self.text = text
        self.count = count
        self.limit = limit
        self.deadline = deadline
        self.taken = False
        self.abandoned = False
        self.reply: SimpleQueue[list[bytes] | BaseException | None] = SimpleQueue()


class _Helper:
    """The thread that alone talks to this process's worker, taking requests in turn. It is
    started with `_thread`, which, unlike `threading`, takes no lock in the calling thread that
    an exception there could leave held."""

    def __init__(self) -> None:
        self.owner = os.getpid()
        self.requests: SimpleQueue[_Request] = SimpleQueue()
        self.worker: _Worker | None = None
        self.numbers = 0
        self.alive = True  # until the thread ends, having taken its last request
        try:
            _thread.start_new_thread(self._run, ())
        except RuntimeError as error:
            raise _cant_start(error) from None

    def _run(self) -> None:
        try:
            while True:
                try:
                    request = self.requests.get(timeout=_IDLE)
                except Empty:
                    if _helper is not self:  # replaced: end, with the worker
                        self.alive = False
                        self._drop()
                        return
                    continue
                request.taken = True
                self._serve(request)
        finally:
            self.alive = False

    def _serve(self, request: _Request) -> None:
        if request.abandoned:
            return
        if request.stop:
            try:
                self._drop(kill=False)
            finally:
                request.reply.put(None)
        elif time.monotonic() >= request.deadline:
            request.reply.put(_too_long(request.limit))  # the worker stays in step
        else:
            try:
                request.reply.put(self._exchange(request))
            except Exception as error:  # noqa: BLE001 - every error goes to its caller
                request.reply.put(error)

    def _exchange(self, request: _Request) -> list[bytes]:
        """One request and its reply. A worker that is out of step afterwards is killed."""
        worker = self._current()
        self.numbers += 1
        number = str(self.numbers).encode()
        message = frames(number, request.names, request.text)
        try:
            outputs = worker.exchange(number, message, request)
        except TransformError, WorkerError:
            raise  # the whole reply was read: the worker is in step
        except BrokenPipeError, EOFError:
            self.worker = None
            raise worker.died() from None
        except _OutOfStepError:
            self.worker = None
            raise worker.died("answered another request") from None
        except BaseException:
            self._drop()
            raise
        if outputs is None:
            self._drop()
            raise _too_long(request.limit)
        return outputs

    def _current(self) -> _Worker:
        """The worker, started anew where there is none or it has ended."""
        if self.worker is not None and self.worker.process.poll() is not None:
            _LOGGER.warning(
                "Saxon's worker %d had ended (exit code %d); starting a new one",
                self.worker.process.pid,
                self.worker.process.returncode,
            )
            self._drop()
        if self.worker is None:
            self.worker = _Worker()
        return self.worker

    def _drop(self, *, kill: bool = True) -> None:
        worker, self.worker = self.worker, None
        if worker is not None:
            worker.stop(kill=kill)


_helper: _Helper | None = None


def _current_helper() -> _Helper:
    """This process's helper, started where there is none. Two threads that start one at once
    each get their own, with their own worker; the one not kept ends when it is idle."""
    global _helper
    if os.name != "posix":
        raise WorkerError("the worker for the official rules needs a POSIX system")
    helper = _helper
    if helper is None or helper.owner != os.getpid() or not helper.alive:
        helper = _Helper()
        _helper = helper
    return helper


def _after_fork() -> None:
    """In a forked child: close its copies of the pipes of the parent's workers; the next call
    starts a helper and worker of its own."""
    global _helper, _starting
    _helper = None
    _starting = threading.RLock()
    for worker in list(_workers):
        worker.forget()
    _workers.clear()


# Windows has no fork; there no worker is started (`_current_helper`), and Haflinger still
# imports and reads invoices.
_register_at_fork = getattr(os, "register_at_fork", None)
if _register_at_fork is not None:
    # `_starting` is looked up at each fork, as a child replaces it.
    _register_at_fork(
        before=lambda: _starting.acquire(),
        after_in_parent=lambda: _starting.release(),
        after_in_child=_after_fork,
    )


def transform(
    data: bytes, *stylesheets: str, timeout: float | None = None, started: float | None = None
) -> list[bytes]:
    """Apply each stylesheet, a path below `ARTEFACTS`, to XML that `_xml.parse` has accepted,
    so that it holds no DTD and no entity. Saxon gets the document as received, decoded by the
    encoding the XML parser accepted, and parses it once: a tree written out again would have
    other namespace prefixes and no comments, and some rules see that (REQ-002-PRS-F006); a
    file would put the input on disk (REQ-001-PRS-NF001). The time limit, `time_limit(timeout)`,
    counts from `started`, by default now, and includes waiting for another thread's call,
    starting the worker and compiling the stylesheets."""
    limit = time_limit(timeout)
    deadline = (time.monotonic() if started is None else started) + limit
    request = _Request(
        "\n".join(stylesheets).encode(), decode(data).encode(), len(stylesheets), limit, deadline
    )
    try:
        reply = _handed(request)
    except BaseException:
        # The helper skips the request if it hasn't begun it, or kills the worker if it has.
        request.abandoned = True
        raise
    if isinstance(reply, BaseException):
        raise reply
    if reply is None:
        raise AssertionError  # only a request to stop gets None
    return reply


def _handed(request: _Request) -> list[bytes] | BaseException | None:
    """Hand `request` to the helper and wait for its reply. A helper that ended without taking
    it, one not kept that a thread held up got, hands it on to the current one."""
    helper = _current_helper()
    helper.requests.put(request)
    while True:
        try:
            left = max(request.deadline - time.monotonic(), 0)
            return request.reply.get(timeout=min(left, _SLICE))
        except Empty:
            pass
        if time.monotonic() >= request.deadline:
            raise _too_long(request.limit)
        if not helper.alive:
            if request.taken:  # its reply, if any, came before it ended
                try:
                    return request.reply.get_nowait()
                except Empty:
                    raise WorkerError(
                        "Haflinger's thread for the official rules ended during the call"
                    ) from None
            helper = _current_helper()
            helper.requests.put(request)


def worker_pid() -> int | None:
    """The process ID of this process's worker, if one runs."""
    helper = _helper
    if helper is None or helper.owner != os.getpid():
        return None
    worker = helper.worker
    return None if worker is None else worker.process.pid


def clear_caches() -> None:
    """Stop the worker, so that the next call starts a new one, which compiles its stylesheets
    again and reads them from `ARTEFACTS` as it is then."""
    helper = _helper
    if helper is not None and helper.owner == os.getpid() and helper.alive:
        stop = _Request(b"", b"", 0, 10.0, time.monotonic() + 10, stop=True)
        helper.requests.put(stop)
        try:
            stop.reply.get(timeout=10)
        except Empty:
            stop.abandoned = True
            raise WorkerError("the worker for the official rules didn't stop within 10 s") from None
