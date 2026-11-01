# KoSIT validator configuration for XRechnung

The files of KoSIT's validator configuration that Haflinger uses, unchanged and at their paths in the release: the scenario file, which says which rules run for which invoice and at which levels; the compiled Schematron rules (XSLT), CEN's EN 16931 rules and KoSIT's XRechnung rules, for CII and UBL; and the XML Schema of CII D16B.

|  |  |
| :- | :- |
| **Source** | [itplr-kosit/validator-configuration-xrechnung](https://github.com/itplr-kosit/validator-configuration-xrechnung), release asset `xrechnung-3.0.2-validator-configuration-2026-08-31.zip` |
| **Release** | `v2026-08-31`: XRechnung 3.0.2, XRechnung Schematron 2.6.0, CEN Schematron 1.3.16 |
| **Commit** | `b436fc4bf05ad501ab5cbb4a53fdffee3d4e18be` |
| **SHA-256 of the ZIP** | `2530cd107c414511c5d0462ec10f886910395abfca820db82e83d70bf01221a8` |
| **Licence** | The configuration is Apache-2.0, see [LICENSE](LICENSE), taken from the repository at the release's commit because the ZIP has none. CEN's EN 16931 rules (`EN16931-*-validation.xsl`) are EUPL-1.2, see [LICENSE-EUPL-1.2.txt](LICENSE-EUPL-1.2.txt), taken from CEN's [eInvoicing-EN16931](https://github.com/ConnectingEurope/eInvoicing-EN16931) at tag `validation-1.3.16`. The XML Schema is © UN/CEFACT (2016) and may be copied and distributed unchanged with its copyright notice, which is in the header of each file. |

| File | Used for |
| :- | :- |
| `scenarios.xml` | The rule sets of XRechnung 3.0, its extension, CVD and plain EN 16931, with the XML Schema each checks first, and KoSIT's rule levels (`customLevel`) |
| `resources/cii/16b/xsl/EN16931-CII-validation.xsl`, `resources/ubl/2.1/xsl/EN16931-UBL-validation.xsl` | CEN's EN 16931 rules, compiled by KoSIT with SchXslt 1.10.1; they differ from the XSLT in CEN's own release, which is compiled with the ISO skeleton |
| `resources/xrechnung/3.0.2/xsl/XRechnung-CII-validation.xsl`, `resources/xrechnung/3.0.2/xsl/XRechnung-UBL-validation.xsl` | KoSIT's XRechnung rules |
| `resources/cii/16b/xsd/*.xsd` | The CII D16B XML Schema, for incoming and written invoices; the entry point is `CrossIndustryInvoice_100pD16B.xsd`. The files keep their CRLF line endings. |
| `resources/ubl/2.1/xsd/maindoc/UBL-Invoice-2.1.xsd`, `resources/ubl/2.1/xsd/maindoc/UBL-CreditNote-2.1.xsd`, `resources/ubl/2.1/xsd/common/*.xsd` | The UBL 2.1 XML Schema of invoices and credit notes, for incoming invoices |

Not included: the UBL 2.1 XML Schemas of the other document types; the report stylesheets; the copies of the CEN rules at the top level of the ZIP, which are identical to those under `resources/`; the changelog and usage notes.

To update: [development guide](../../../../docs/guides/development.md#updating-official-files).
