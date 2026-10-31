# FeRD's ZUGFeRD package: Factur-X rules and XML Schemas

The Schematron rules and XML Schemas of FeRD's ZUGFeRD package for the five Factur-X profiles (MINIMUM, BASIC WL, BASIC, EN 16931, EXTENDED), unchanged and at their paths in the package. Haflinger compiles each Schematron with [SchXslt](../schxslt/README.md) on first use and validates Factur-X and ZUGFeRD invoices with it ([REQ-002-PRS-F003](../../../../docs/specs/req-002-conformance.md#req-002-prs-f003-rule-sets)); the EN 16931 profile's XML Schema checks the invoices Haflinger writes ([REQ-004-PRS-F004](../../../../docs/specs/req-004-outgoing-invoices.md#req-004-prs-f004-xml-schema)).

|  |  |
| :- | :- |
| **Source** | FeRD's [ZUGFeRD package](https://www.ferd-net.de/en/downloads/publications), English edition, archive `ZUGFeRD_2.5.2_EN.zip`, downloaded by the maintainer through FeRD's form |
| **Release** | ZUGFeRD 2.5.2, technically identical to Factur-X 1.09.2, released 2026-08-04, effective 2026-09-01 |
| **Commit** | none: FeRD publishes no repository; the archive is identified by its SHA-256 |
| **SHA-256 of the ZIP** | `03c335f0b898a66a14d2548ee5dfe72504d0138a732c4e67e805866f45fc5ebf` |
| **Licence** | Apache-2.0: "For the use of the ZUGFeRD Technical Artifacts (Schemata and Schematron) the Apache 2.0 license conditions apply" (FeRD's [disclaimer and rights of use](https://www.ferd-net.de/en/ueber-uns/ressourcen-1/veroeffentlichungen/disclaimer-and-rights-of-use-zugferd)). The package has no licence file; [LICENSE](LICENSE) is the licence's text from apache.org. |

| File, per profile folder `Schema/<n>_Factur-X_1.09.2_<PROFILE>/` | Used for |
| :- | :- |
| `FACTUR-X_<PROFILE>.sch` | The profile's rules, compiled with SchXslt |
| `FACTUR-X_<PROFILE>_codedb.xml` | The code lists the Schematron reads with `document()`; part of the Schematron |
| `Factur-X_1.09.2_<PROFILE>.xsd` and its three imports | The profile's XML Schema; Haflinger uses the EN 16931 profile's |

Not included:

- FeRD's XSLT compiled from the Schematron (`_XSLT_<PROFILE>/`): the rights of use don't name it, so Haflinger compiles the Schematron itself;
- the sample invoices (`Examples/`): no terms name them ([ITEM-002](../../../../docs/backlog/item-002-official-test-material.md));
- the documentation, the spreadsheets, the logos (whose use FeRD rules separately) and the full CII D22B XML Schema.

To update: [development guide](../../../../docs/guides/development.md#updating-official-files); FeRD's package is downloaded through FeRD's form.
