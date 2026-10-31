# KoSIT XRechnung visualisation

The stylesheets of KoSIT's visualisation that turn a CII invoice, a UBL invoice or a UBL credit note into KoSIT's semantic XML, in which every element carries its business term ID; unchanged and at their paths in the release. Haflinger's tests read official and written invoices through them as an independent second reader ([ADR-005](../../../../docs/arc42/adr/ADR-005-own-mapping-kosit-as-check.md)).

|  |  |
| :- | :- |
| **Source** | [itplr-kosit/xrechnung-visualization](https://github.com/itplr-kosit/xrechnung-visualization), release asset `xrechnung-3.0.2-visualization-2026-10-13.zip` |
| **Release** | `v2026-10-13`: XRechnung 3.0.2; it fixes script injection through attachment file names (BT-122, BT-125) in the HTML step |
| **Commit** | `811903564db35438abdb3e24fb6cfd37b92dbf78` |
| **SHA-256 of the ZIP** | `ecf3913029218822ee4c90a86a3e23689768bf3568a061cf9bc742115e52264e` |
| **Licence** | Apache-2.0, see [LICENSE](LICENSE), taken from the repository at the release's commit because the ZIP has none |

| File | Used for |
| :- | :- |
| `xsl/cii-xr.xsl`, `xsl/ubl-invoice-xr.xsl`, `xsl/ubl-creditnote-xr.xsl` | CII, UBL invoice and UBL credit note into the semantic XML |
| `xsl/common-xr.xsl`, `xsl/functions.xsl` | Included by the three above |
| `xsl/l10n/de.xml`, `xsl/l10n/en.xml` | Texts `functions.xsl` loads |
| `xsd/xrechnung-semantic-model.xsd` | The schema of the semantic XML |

Not included: the HTML and PDF steps with their scripts, styles, fonts and FOP configuration, which rendering invoices for people would need ([ITEM-005](../../../../docs/backlog/item-005-rendering.md)); the release's test invoices; the documentation and changelog.

To update: [development guide](../../../../docs/guides/development.md#updating-official-files).
