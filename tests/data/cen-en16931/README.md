# CEN EN 16931 unit tests

CEN's per-rule unit tests for the EN 16931 rules, unchanged and at their paths in the repository. Each file is a VEFA `testSet`: each `<test>` holds an invoice fragment and an `<assert>` with the rule IDs expected to succeed (`<success>`) or fail (`<error>`, `<warning>`).

|  |  |
| :- | :- |
| **Source** | [ConnectingEurope/eInvoicing-EN16931](https://github.com/ConnectingEurope/eInvoicing-EN16931), `test/` at the release's tag; the release assets hold no tests |
| **Release** | `validation-1.3.16`: the release of the EN 16931 rules in KoSIT's [validator configuration](../../../src/haflinger/artefacts/kosit-validator-xrechnung/README.md) |
| **Commit** | `b6c9e06a59812fb1a83585da40923b3678a649ad` |
| **Licence** | EUPL-1.2, see [LICENSE.txt](LICENSE.txt) |

| Folder | Files | Tests | What they are |
| :- | :- | :- | :- |
| `test/Invoice-unit-UBL/` | 206 | 732 | Unit tests on UBL invoices |
| `test/CreditNote-unit-UBL/` | 71 | 172 | Unit tests on UBL credit notes |
| `test/cii/` | 2 | 9 | Unit tests on CII invoices (`BR-CO-15`, `BR-CO-17`) |

Each file is byte for byte the blob at the commit (checked with `git hash-object --no-filters`); a checkout can change line endings through the repository's attributes.

Not included: the examples (`cii/examples/`, `ubl/examples/`), the Peppol BIS test files (`test/testfiles/`), the rules and schemas, which Haflinger takes from KoSIT's configuration.

To update: [development guide](../../../docs/guides/development.md#updating-official-files).
