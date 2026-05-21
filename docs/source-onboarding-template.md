# Source Onboarding Template

Use this template whenever adding a new source.

## Source Identity

- `source_id`:
- `source_name`:
- `jurisdiction`:
- `government_level`:
- `body_name`:
- `source_type`:
- `collection_method`:

## Collection Details

- `base_url`:
- `email_sender_patterns`:
- `attachment_patterns`:
- `meeting_frequency`:
- `priority_level`:
- `status`:

## Retrieval Notes

- How do documents arrive?
- Are attachments sent directly or linked externally?
- Are multiple document types bundled together?
- Is this source scriptable?
- What are the naming quirks?

## Parsing Notes

- How is meeting date represented?
- How is item numbering represented?
- Are there stable agenda sections?
- Are OCR problems likely?

## Relevance Notes

- Likely issue areas:
- Likely cross-cutting tags:
- Expected signal quality:

## Activation Checklist

1. Add config entry.
2. Test sample ingestion.
3. Verify filename normalization.
4. Verify text extraction.
5. Review extracted metadata quality.
6. Mark source active.
