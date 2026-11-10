# ADR-011: Attached documents in the model, as bytes, within the input's size limit

| Meta | Value |
| :- | :- |
| **Status** | Proposed |
| **Date** | 2026-11-08 |
| **Author** | loxy (drafted with Claude) |

## Context

A supporting document (BG-24) may carry the document itself, embedded in the invoice: the attached document (BT-125), with its media type (BT-125-1, `mimeCode`) and file name (BT-125-2, `filename`), such as a timesheet as a PDF. CII writes it as `ram:AttachmentBinaryObject` of an `ram:AdditionalReferencedDocument` with the type code `916`, UBL as `cac:AdditionalDocumentReference/cac:Attachment/cbc:EmbeddedDocumentBinaryObject`; both hold the file's bytes as Base64 text in the XML (`xs:base64Binary`, which allows whitespace between its characters). The model holds every other term of the supporting document (REQ-001-PRS-F001); BT-125 is the last term of KoSIT's test suite it doesn't, so a model read and written again loses the attachments.

- **The official files**: 36 attachments in 32 files of KoSIT's test suite, all PDFs with a file name; 18 in 13 files of the ZUGFeRD corpus, PDFs, PNGs and one `application/octet-stream`. The largest is 1.1 MB of Base64, about 0.8 MB of file. None of them breaks its Base64 into lines, and their XML Schemas refuse text that isn't Base64.
- **The official rules**: CEN's `BR-CL-24` checks the media type against its list (PDF, PNG, JPEG, CSV, the spreadsheet formats of Excel and OpenDocument); `UBL-DT-06` and `UBL-DT-07` require a UBL attachment's media type and file name; XRechnung's `BR-DE-22` requires unique file names; CEN's `CII-SR-476`, a warning, allows one attachment among a CII invoice's supporting documents, where EN 16931 and UBL allow one for each; KoSIT's scenarios lower it to information for XRechnung, as its context is wrong, and check one for each supporting document instead (`BR-TMP-5`, a warning). Factur-X BASIC has no attachments; EN 16931 and EXTENDED have them.
- **Size**: every input is refused above `max_size`, by default 100 MiB, before it is parsed (REQ-001-PRS-NF003). An attachment is part of the XML, so it already counts against that limit, and its decoded bytes are three quarters of its Base64 text.
- **Outside input**: an attachment is a file from the sender. Haflinger already treats incoming XML as hostile (`defusedxml`, ADR-003); the app scans incoming files, and offers PDFs as a download rather than rendering them ([ITEM-003](../../backlog/item-003-erpnext-app.md)). KoSIT's release of 2026-10-13 fixed script injection through attachment file names in its rendering ([ITEM-005](../../backlog/item-005-rendering.md)).
- **ZUGFeRD PDFs**: Factur-X lets the PDF carry further files beside the invoice XML. Those are files of the PDF, not EN 16931 terms; BT-125 is inside the XML.

## Decision

- **The model holds an attachment as bytes**: `SupportingDocument.attachment`, an `Attachment` with `content` (BT-125, the decoded bytes), `mime_code` (BT-125-1) and `filename` (BT-125-2), each as written. Reading decodes the Base64 text with the standard library, after removing the whitespace `xs:base64Binary` allows; text that isn't Base64 as `xs:base64Binary` defines it is missing, with a `HAFL-VALUE` finding (REQ-003-PRS-F002), also where only its last characters carry bits beyond its bytes, which Python's decoder ignores. Writing encodes the bytes as Base64 without line breaks. The Base64 text is notation, like the digits a number is written with, and REQ-001-URS-NF001 gains that exception: the bytes stay exactly as they are, the text that carries them may change.
- **No limit of its own**: an attachment counts against the input's `max_size`, as now; a caller that wants smaller attachments passes a smaller `max_size`. A model with an attachment is written as any other: the document written is refused after writing when validation can't take its size (REQ-004-PRS-F001).
- **Haflinger never opens an attachment**: it reads, compares and writes the bytes, and neither looks into them, renders them nor checks that they are what the media type says. The media type and the file name are read and written as text; the official rules check the media type (`BR-CL-24`) and the file names' uniqueness (`BR-DE-22`), and Haflinger adds no list of its own (ADR-003). The file name is outside input: Haflinger never uses it as a path. An attachment without its media type or file name, which EN 16931 requires, is read as it is; writing refuses it, since no official rule checks either in CII D16B (REQ-004-PRS-F001), as it refuses a card without its account number.
- **An attachment shows as its name, type and size**: the `Attachment`'s `repr` gives `filename`, `mime_code` and the length of `content`, not the bytes, so that a model printed in a log or a failing test stays readable. Equality compares the bytes.
- **Each supporting document holds at most one attachment**, as EN 16931 does; a model with attachments in several supporting documents is written, and CEN's `CII-SR-476` warns of it in CII, which doesn't stop the invoice being handed out (REQ-002-PRS-F002).
- **ZUGFeRD PDFs**: `embed` leaves the attachments in the XML, where EN 16931 puts them; files of the PDF beside the invoice are not read and not written.

## Alternatives Considered

### Alternative 1: The Base64 text as written

The model holds the text between the tags, and callers decode it.

Its advantage: writing copies the text unchanged, and REQ-001-URS-NF001 needs no exception.

**Rejected because** BT-125 is the document, not its notation: every caller wants the file, so each would decode the text, and an app sending a file would encode it. Two invoices with the same file would also differ where one breaks its Base64 into lines, which `xs:base64Binary` allows, though none of the official files does (REQ-003-PRS-F004).

### Alternative 2: Leave attachments in the original

As for XRechnung's extension (ADR-007): the model doesn't hold them, the archived original does.

**Rejected because** BT-125 is a term of EN 16931, not an extension: the operator needs the timesheet beside the invoice, and an invoice the app writes needs to carry one, which the model can't hold without the term.

### Alternative 3: A reference to the attachment instead of its bytes

The model holds where to find the bytes, a file path or a callable that decodes them on demand.

**Rejected because** the library stores nothing, and where files go is the app's choice (ERPNext's files, ADR-001); decoding on demand would keep the parsed XML alive with the model. The bytes are at most three quarters of an input Haflinger has already read whole.

### Alternative 4: A size limit for attachments

A separate keyword argument, below `max_size`, for the attachments alone.

**Rejected because** `max_size` already bounds them, and no official file comes near it; a second limit adds a refusal and a parameter without a need. Reconsidered when a caller needs one (trigger 2).

## Consequences

### Positive

- The model holds every term of KoSIT's test suite: a model read and written again keeps its attachments, and the app can store them beside the invoice.
- The CII and the UBL file of an invoice read to the same attachment, whatever their Base64's line breaks.
- An attachment's content stays opaque to Haflinger, so no file format adds attack surface to it.

### Negative

- Reading holds an attachment twice for a moment, as Base64 text in the parsed XML and as bytes in the model: about 1.75 times its Base64 text, and 2.75 times where the text holds whitespace, which is removed in a copy; within what `max_size` allows.
- The written XML carries the same bytes as the original but not always the same text, so the original remains the invoice that is archived (ADR-007).
- A CII invoice with more than one attachment carries a warning (`CII-SR-476`) that a UBL one doesn't.

## Reconsideration Triggers

1. EN 16931-1:2026 or its bindings change the attached document, for example to allow more than one per supporting document.
2. A caller needs attachments refused below `max_size`, or invoices whose attachments approach it are common: then a limit of their own, or streaming.
3. ZUGFeRD or the app needs the files of a PDF beside its invoice.

## Compliance

- Haflinger SHALL NOT open, render or execute an attachment's content, and SHALL NOT use its file name as a path.
- An attachment's `repr` SHALL NOT include its content.
- Haflinger SHALL NOT check media types beyond the official rules.

## References

- Affects: REQ-001 (the model, REQ-001-URS-NF001's exceptions), REQ-003 (reading BT-125), REQ-004 (writing BT-125), arc42 [§8](../README.md#8-cross-cutting-concepts)
- [ADR-001](ADR-001-library-and-app.md), [ADR-003](ADR-003-integrate-dont-implement.md), [ADR-007](ADR-007-model-scope-and-editions.md), [ITEM-003](../../backlog/item-003-erpnext-app.md), [ITEM-005](../../backlog/item-005-rendering.md)
