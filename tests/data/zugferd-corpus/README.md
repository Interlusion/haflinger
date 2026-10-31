# ZUGFeRD corpus: Mustang's PDFs

A selection of the ZUGFeRD corpus, unchanged and at their paths in the repository: PDFs made by the Mustang project, whose author keeps the corpus. Haflinger's tests read ZUGFeRD PDFs through them, valid and broken (REQ-003-PRS-F007, REQ-003-PRS-NF003).

|  |  |
| :- | :- |
| **Source** | [ZUGFeRD/corpus](https://github.com/ZUGFeRD/corpus), branch `master`; the corpus has no releases |
| **Release** | none; the commit below, of 2026-10-13 |
| **Commit** | `82e886fb21369e3e83c1e97170a4ff406deceee7` |
| **Licence** | Apache-2.0, see [LICENSE](LICENSE), taken from the repository's root at the commit |

| File | Embedded file | Used for |
| :- | :- | :- |
| `ZUGFeRDv2/correct/Mustangproject/MustangGnuaccountingBeispielRE-20190610_507.pdf` | `zugferd-invoice.xml`, EN 16931 | Reading a ZUGFeRD 2.0 PDF |
| `ZUGFeRDv2/correct/Mustangproject/MustangGnuaccountingBeispielRE-20201121_508.pdf` | `factur-x.xml`, EN 16931 | Reading a ZUGFeRD 2.1 / Factur-X PDF |
| `ZUGFeRDv2/correct/Mustangproject/MustangGnuaccountingBeispielRE-20201121_508_withBOM.pdf` | `factur-x.xml` starting with a UTF-8 byte order mark | Handing out the embedded file byte for byte |
| `ZUGFeRDv2/fail/MustangRE-20171118_506_ZUGFeRD1and2.pdf` | `ZUGFeRD-invoice.xml` (ZUGFeRD 1.0) and `factur-x.xml` | The refusal of a PDF with more than one invoice |
| `ZUGFeRDv2/fail/Mustangproject/MustangGnuaccountingBeispielRE-20171118_506.pdf` | `factur-x.xml`, EXTENDED in the spelling `urn:cen.eu:en16931:2017:compliant:factur-x.eu:1p0:extended` | An alternative spelling of BT-24 (REQ-002-PRS-F003) |
| `ZUGFeRDv2/fail/Mustangproject/factur-x-invalid-xml-encoding-attribute.pdf` | `factur-x.xml` declaring the encoding `UTF-8-W/O-BOM` | The refusal of an embedded file that isn't readable XML |
| `ZUGFeRDv2/fail/Mustangproject/wrongFilename.pdf` | `factur-y.xml` | The refusal of a PDF with no invoice under a known name |
| `ZUGFeRDv1/correct/Mustangproject/MustangGnuaccountingBeispielRE-20170509_505.pdf` | `ZUGFeRD-invoice.xml`, ZUGFeRD 1.0 EXTENDED | The refusal of ZUGFeRD 1.0, named, inside a PDF |

Every PDF declares PDF/A-3U in its XMP metadata. Each file is byte for byte the blob at the commit (checked with `git hash-object --no-filters`).

Not included: the rest of the corpus. Most of its ZUGFeRD PDFs are FeRD's official samples and FNFE-MPE's Factur-X examples, which the corpus redistributes; their own terms don't name the samples, so they wait for FeRD's package ([ITEM-002](../../../docs/backlog/item-002-official-test-material.md)). The two large Peppol invoices stay out too; the benchmarks use a local clone ([development guide](../../../docs/guides/development.md#running-the-zugferd-corpus)).

To update: [development guide](../../../docs/guides/development.md#updating-official-files).
