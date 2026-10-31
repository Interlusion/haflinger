# veraPDF corpus: one PDF/A file

One file of veraPDF's test corpus, unchanged and at its path in the repository: a one-page PDF/A-2b document ("Hello World", with an embedded font subset) that veraPDF's test suite marks as passing. Haflinger's tests embed invoices into it as the PDF a caller rendered (REQ-004-PRS-F007).

|  |  |
| :- | :- |
| **Source** | [veraPDF/veraPDF-corpus](https://github.com/veraPDF/veraPDF-corpus), by the veraPDF Consortium |
| **Release** | `v1.28.1`, the latest tag |
| **Commit** | `eb5344d4712aed8ada477828101005d63d141fbb` |
| **Licence** | CC BY 4.0, as the repository's README states; the legal code is in [LICENSE](LICENSE), taken from [creativecommons.org](https://creativecommons.org/licenses/by/4.0/legalcode.txt) because the repository has no licence file. The file is unchanged. |

| File | Used for |
| :- | :- |
| `PDF_A-2b/6.2 Graphics/6.2.11 Fonts/6.2.11.4 Embedding/6.2.11.4.2 Subset embedding/veraPDF test suite 6-2-11-4-2-t02-pass-a.pdf` | The PDF/A input of `haflinger.pdf.embed` |

The file is byte for byte the blob at the commit (checked with `git hash-object --no-filters`).

Not included: the rest of the corpus, which tests PDF/A validators.

To update: [development guide](../../../docs/guides/development.md#updating-official-files).
