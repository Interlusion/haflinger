# ZUGFeRD corpus: a selection

A selection of the ZUGFeRD corpus, unchanged and at their paths in the repository: PDFs made by the Mustang project, whose author keeps the corpus, and broken invoices of other producers of a profile KoSIT's validator has rules for. Haflinger's tests read ZUGFeRD PDFs through them, valid and broken (REQ-003-PRS-F007, REQ-003-PRS-NF003), and compare `validate` with KoSIT's validator over the broken invoices (REQ-002-PRS-F007).

|  |  |
| :- | :- |
| **Source** | [ZUGFeRD/corpus](https://github.com/ZUGFeRD/corpus), branch `master`; the corpus has no releases |
| **Release** | none; the commit below, of 2026-10-13 |
| **Commit** | `82e886fb21369e3e83c1e97170a4ff406deceee7` |
| **Licence** | Apache-2.0, see [LICENSE](LICENSE), taken from the repository's root at the commit; the corpus passes on the other producers' files under it, which name no licence of their own |

| File | Embedded file | Used for |
| :- | :- | :- |
| `ZUGFeRDv2/correct/Mustangproject/MustangGnuaccountingBeispielRE-20190610_507.pdf` | `zugferd-invoice.xml`, EN 16931 | Reading a ZUGFeRD 2.0 PDF |
| `ZUGFeRDv2/correct/Mustangproject/MustangGnuaccountingBeispielRE-20201121_508.pdf` | `factur-x.xml`, EN 16931 | Reading a ZUGFeRD 2.1 / Factur-X PDF |
| `ZUGFeRDv2/correct/Mustangproject/MustangGnuaccountingBeispielRE-20201121_508_withBOM.pdf` | `factur-x.xml` starting with a UTF-8 byte order mark | Handing out the embedded file byte for byte |
| `ZUGFeRDv2/fail/MustangRE-20171118_506_ZUGFeRD1and2.pdf` | `ZUGFeRD-invoice.xml` (ZUGFeRD 1.0) and `factur-x.xml` | The refusal of a PDF with more than one invoice |
| `ZUGFeRDv2/fail/Mustangproject/MustangGnuaccountingBeispielRE-20171118_506.pdf` | `factur-x.xml`, EXTENDED in the spelling `urn:cen.eu:en16931:2017:compliant:factur-x.eu:1p0:extended` | An alternative spelling of BT-24 (REQ-002-PRS-F003) |
| `ZUGFeRDv2/fail/Mustangproject/factur-x-invalid-xml-encoding-attribute.pdf` | `factur-x.xml` declaring the encoding `UTF-8-W/O-BOM` | The refusal of an embedded file that isn't readable XML |
| `ZUGFeRDv2/fail/Mustangproject/wrongFilename.pdf` | `factur-y.xml` | The refusal of a PDF with no invoice under a known name |
| `ZUGFeRDv2/fail/Mustangproject/MustangGnuaccountingBeispielRE-20190610_507a.pdf`, `…_507b.pdf` | `zugferd-invoice.xml`, EN 16931, with `ram:BuyerReference` where CII's XML Schema doesn't allow it | KoSIT's validator over an invoice failing the XML Schema |
| `ZUGFeRDv2/fail/FNFE-factur-x-examples/Avoir_FR_type380_EN16931.pdf`, `Avoir_FR_type381_EN16931.pdf` | `factur-x.xml`, EN 16931, credit notes by FNFE-MPE failing `CII-DT-031` (an amount with a `currencyID`), with a payment reference (BT-83) but no payment means | KoSIT's validator over a broken invoice; a payment reference that KoSIT's reading stylesheet loses |
| `ZUGFeRDv2/fail/FNFE-factur-x-examples/Facture_DOM_EN16931.pdf`, `Facture_FR_EN16931.pdf`, `Facture_UE_EN16931.pdf` | `factur-x.xml`, EN 16931, invoices by FNFE-MPE failing `CII-DT-031`, the last `BR-IC-11` too | KoSIT's validator over a broken invoice |
| `ZUGFeRDv2/fail/ZUGFeRD_2.0_fully_compliant_complete.pdf` | `factur-x.xml`, EN 16931, FeRD's ZUGFeRD 2.0 sample failing `BR-CL-23` and `BR-S-02` | KoSIT's validator over a broken invoice |
| `ZUGFeRDv1/correct/Mustangproject/MustangGnuaccountingBeispielRE-20170509_505.pdf` | `ZUGFeRD-invoice.xml`, ZUGFeRD 1.0 EXTENDED | The refusal of ZUGFeRD 1.0, named, inside a PDF |

Every PDF declares PDF/A-3 in its XMP metadata: Mustang's as 3U, FNFE-MPE's as 3B, FeRD's as 3A. Each file is byte for byte the blob at the commit (checked with `git hash-object --no-filters`).

Not included: the rest of the corpus. Most of its ZUGFeRD PDFs are FeRD's official samples and FNFE-MPE's Factur-X examples, which wait for the selection [ITEM-002](../../../docs/backlog/item-002-official-test-material.md) plans. Of its broken invoices, those of a profile KoSIT's validator has no rules for, such as BASIC or MINIMUM, those broken only as PDFs, and ZUGFeRD 1.0 stay out, and so does an XRechnung invoice whose names and addresses are scrambled but whose VAT identifiers and IBAN pass their check digits, as real ones do. The two large Peppol invoices stay out too; the benchmarks use a local clone ([development guide](../../../docs/guides/development.md#running-the-zugferd-corpus)).

To update: [development guide](../../../docs/guides/development.md#updating-official-files).
