# ADR-012: Two public modules, the rest private, the API what their `__all__` lists

| Meta | Value |
| :- | :- |
| **Status** | Proposed |
| **Date** | 2026-11-11 |
| **Author** | loxy (drafted with Claude) |

## Context

The specs define five entry points, `read_invoice`, `validate` and `write_cii` in `haflinger` and `extract_xml` and `embed` in `haflinger.pdf`, with the model's classes, `ReadResult`, `Finding` and the two errors, which `haflinger.__all__` exports. The package holds more: besides `haflinger.pdf`, nine modules without a leading underscore (`errors`, `findings`, `model`, `read`, `cii`, `ubl`, `kosit`, `validation`, `write`), whose names Python's convention marks as public, though no spec defines them. Some skip what the entry points guarantee:

- `haflinger.kosit.read_invoice`, the tests' second reader ([ADR-005](ADR-005-own-mapping-kosit-as-check.md)), takes no `max_size` and takes minutes on large files;
- `haflinger.validation.check_rules` runs the rules without the XML Schema check first (REQ-002-PRS-F011);
- `haflinger.cii.write` writes CII without any check (REQ-004-PRS-F004, REQ-004-PRS-F005).

None of the submodules has an `__all__`, so nothing tells their public names from their helpers. What a caller needs is missing at the same time: `Flag`, the type of a finding's flag, `Syntax`, the type of the syntax an invoice was read from, and the target profiles of writing, which a caller needs to choose BT-24 before `write_cii`, aren't exported, and the rule that an invoice is valid when no finding is `fatal` or `error` lives only in the spec (REQ-002-PRS-F002), so each caller would write it again. `validate` returns a `list`, while `ReadResult.findings` and `InvoiceWriteError.findings` are tuples. The package's docstring is one line.

Haflinger isn't released, and the ERPNext app isn't written yet ([ITEM-003](../../backlog/item-003-erpnext-app.md)): what the first release exports is what the app and every other caller will build on. Python's style guide asks for internal modules to carry a leading underscore even where `__all__` is set (PEP 8, "Public and Internal Interfaces"). The security policy's scope is already the five entry points.

## Decision

- **Two public modules**: `haflinger` and `haflinger.pdf`. `haflinger.pdf` stays a module of its own, as it needs the extra `pdf` (`pypdf`, `factur-x`), which importing `haflinger` doesn't.
- **Every other module is private**, its name starting with an underscore: `_model`, `_errors`, `_findings`, `_read`, `_cii`, `_ubl`, `_kosit`, `_validation` and `_write`, beside the private ones there already are. The tests and scripts of this repository import them; callers don't.
- **The API is what the two `__all__` list**, nothing else. `haflinger` exports the three entry points, the model's classes (REQ-001-PRS-F001) and `Syntax`, `ReadResult`, `Finding`, `Flag`, `is_valid`, `TARGET_PROFILES` and the two errors; `haflinger.pdf` exports `extract_xml` and `embed`.
- **New exports for what callers need**: `Flag` and `Syntax`, the types of `Finding.flag` and `Invoice.syntax`; `TARGET_PROFILES`, the BT-24 values `write_cii` writes (REQ-004-PRS-F002), as a tuple; and `is_valid(findings)`, a function that applies REQ-002-PRS-F002's rule to `validate`'s findings: no finding with the flag `fatal` or `error`. It judges the rules that ran: a `HAFL-PROFILE` warning says the profile's own rules didn't. Reading's findings are no verdict, and an `InvoiceWriteError` is a refusal whatever findings it holds; `is_valid` is not for them.
- **`validate` returns a tuple** of findings, as `ReadResult.findings` and `InvoiceWriteError.findings` do.
- **Documented in the package**: the docstring of `haflinger` names the entry points and what they hand back, so that `help(haflinger)` says it; the README shows them in use. Generated reference documentation waits for the releases.

## Alternatives Considered

### Alternative 1: `__all__` in each module

The modules keep their names; each declares its public names in `__all__`, and helpers get a leading underscore.

Its advantage: no module is renamed.

**Rejected because** a module without an underscore stays importable and looks public, whatever its `__all__` says, so `haflinger.cii.write` would remain one import away. It also leaves many more names to keep stable: every public name of nine modules, instead of two lists.

### Alternative 2: A result type with validity

`validate` returns an object holding the findings and a property such as `valid`, instead of a sequence.

Its advantage: the verdict travels with the findings.

**Rejected because** `ReadResult.findings` and `InvoiceWriteError.findings` would need the same type to have the same property, and a caller holding findings from any of them needs only the rule. A function serves every sequence of findings, and `validate` stays a function that returns them.

### Alternative 3: Lists everywhere

`ReadResult.findings` and `InvoiceWriteError.findings` become lists, as `validate`'s are.

**Rejected because** the model and its results are frozen: a list in a frozen result could still be changed in place, and a tuple can be hashed and compared like the rest of the model.

### Alternative 4: Public classes that name `haflinger` as their module

Each exported class gets `__module__ = "haflinger"`, so that a traceback shows `haflinger.InvoiceReadError`, not `haflinger._errors.InvoiceReadError`.

**Rejected because** Python finds a class's source through its module: `inspect.getsource`, an editor's jump to the definition and a debugger's source view would fail for every class of the model. It would also stop at classes, as the functions and the type aliases `Flag` and `Syntax` keep their modules.

### Alternative 5: `haflinger.model` public too

The model's classes stay importable from a public `haflinger.model` beside `haflinger`.

**Rejected because** two places to import the same class from are two names to keep stable, and the model's classes are already exported from `haflinger`.

## Consequences

### Positive

- One rule says what a caller may rely on: an underscore anywhere in the import path is internal.
- The names that skip the entry points' guarantees (`check_rules`, the second reader, the unchecked writer) are private.
- A caller chooses a target profile and decides validity with Haflinger's own names, not copies of the spec.
- The API matches the security policy's scope.

### Negative

- Nine modules are renamed: the tests, the scripts and the architecture's names change with them, and `git log --follow` is needed for a file's history.
- Every exported name, `TARGET_PROFILES` and `is_valid` included, is a name to keep stable once released.
- `validate`'s return type changes; no release has the old one.
- Tracebacks and `help` show the private modules the public names are defined in, such as `haflinger._errors.InvoiceReadError`.

## Reconsideration Triggers

1. The ERPNext app, or another caller, needs a name the two modules don't export: export it, with its spec.
2. A third public module is needed, for example for a further syntax, a rule set of Haflinger's own (ADR-003) or a reader of an extension (ADR-007).
3. The releases bring generated reference documentation, which may replace the docstring's list.

## Compliance

- Every module of the package other than `haflinger` and `haflinger.pdf` SHALL have a name that starts with an underscore.
- `haflinger.__all__` and `haflinger.pdf.__all__` SHALL list exactly the names REQ-001-PRS-F006 names.
- A name SHALL be added to them only with the spec that defines it.

## References

- Affects: REQ-001 (the public interface, REQ-001-PRS-F006), REQ-002 (`validate`'s return type, REQ-002-PRS-F001; `is_valid` and `Flag`, REQ-002-PRS-F002), REQ-004 (`TARGET_PROFILES`, REQ-004-PRS-F002), arc42 [§5](../README.md#5-building-block-view), the [security policy](../../../SECURITY.md)
- [ADR-001](ADR-001-library-and-app.md), [ADR-005](ADR-005-own-mapping-kosit-as-check.md), [ITEM-003](../../backlog/item-003-erpnext-app.md)
- [PEP 8, Public and Internal Interfaces](https://peps.python.org/pep-0008/#public-and-internal-interfaces)
