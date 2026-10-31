# SchXslt

The XSLT 2.0 pipeline of SchXslt, a Schematron processor written in XSLT, unchanged and at its paths in the release: it compiles a Schematron schema into the XSLT stylesheet that validates with it. Haflinger compiles FeRD's Factur-X Schematron with it on first use, as KoSIT compiles CEN's rules with the same release ([ADR-006](../../../../docs/arc42/adr/ADR-006-validation-with-official-rules.md)).

|  |  |
| :- | :- |
| **Source** | [SchXslt/schxslt](https://codeberg.org/SchXslt/schxslt) on Codeberg, release asset `schxslt-1.10.1-xslt-only.zip` |
| **Release** | `v1.10.1`, 2024-10-18; the release KoSIT compiles CEN's rules with |
| **Commit** | `17f63a42c2d417206e1289cf767359c4fa047919` (tag `v1.10.1`) |
| **SHA-256 of the ZIP** | `e141fabd4804a0ea527945dc7253dd38f9ef8957d9b219b94e13d16859cff7f0` |
| **Licence** | MIT, see [LICENSE](LICENSE), from the ZIP |

| File | Used for |
| :- | :- |
| `2.0/include.xsl`, `2.0/expand.xsl`, `2.0/compile-for-svrl.xsl` | The three steps that turn a Schematron schema with the XSLT 2.0 query binding into a stylesheet reporting in SVRL |
| `2.0/compile/*.xsl`, `2.0/version.xsl` | Imported by `compile-for-svrl.xsl` |
| `2.0/pipeline.xsl`, `2.0/pipeline-for-svrl.xsl`, `2.0/svrl.xsl`, `2.0/util/normalize-svrl.xsl` | Not used; kept so that the folder is the release's `2.0/` as a whole |

The files are those of the ZIP, which match the sources at the tag except `2.0/version.xsl`, where the build has filled in the version number (`SchXslt/1.10.1`).

Not included: the XSLT 1.0 pipeline, the README, the XProc, Java and database packages of the release.

To update: [development guide](../../../../docs/guides/development.md#updating-official-files).
