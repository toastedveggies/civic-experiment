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
- Do agendas or packets link to prior meeting minutes?
- Do agendas or packets link to staff reports, board letters, presentations, ordinances, or other supporting docs?
- Is this source scriptable?
- What are the naming quirks?

## Parsing Notes

- How is meeting date represented?
- How is item numbering represented?
- Are there stable agenda sections?
- Can we distinguish canonical agendas from minutes and other supporting docs?
- If minutes are linked, can we tell which earlier meeting they describe versus which later meeting approves them?
- Is parliamentary action language present:
  - moved by
  - seconded by
  - final action
  - vote tally
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
6. Verify whether linked minutes and supporting documents should be ingested as first-class documents.
7. Verify whether minutes can be associated to the meeting they describe, not just the approval meeting.
8. Mark source active.
