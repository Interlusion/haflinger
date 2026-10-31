# KoSIT XRechnung test suite

The test invoices of KoSIT's XRechnung test suite, unchanged and at their paths in the release. Each business case comes as a CII file (`_uncefact.xml`), a UBL file (`_ubl.xml`) or both.

|  |  |
| :- | :- |
| **Source** | [itplr-kosit/xrechnung-testsuite](https://github.com/itplr-kosit/xrechnung-testsuite), release asset `xrechnung-3.0.2-testsuite-2026-08-31.zip` |
| **Release** | `v2026-08-31`: XRechnung 3.0.2, the same release as the [validator configuration](../../../src/haflinger/artefacts/kosit-validator-xrechnung/README.md) |
| **Commit** | `44c3905c69ca236aa3b94c04be1b7e9bd066ba03` |
| **SHA-256 of the ZIP** | `1e81ef7563e0fa04c0e0b0631318a7e0843a3c0beb57d83ef95ac0c4a095e3d7` |
| **Licence** | Apache-2.0, see [LICENSE](LICENSE), taken from the repository at the release's commit because the ZIP has none |

| Folder | Files | What they are |
| :- | :- | :- |
| `instances/standard/` | 66 | Business cases of XRechnung 3.0, each as CII and UBL |
| `instances/extension/` | 6 | Business cases of the XRechnung extension |
| `instances/technical-cases/cius/` | 12 | Comprehensive and minimal invoices covering the business terms, each as CII and UBL |
| `instances/technical-cases/cvd/` | 2 | An XRechnung CVD invoice as CII and UBL |

Not included: the release's README, changelog, overview of the cases and development notes. The files keep their line endings (CRLF in most).

To update: [development guide](../../../docs/guides/development.md#updating-official-files).
