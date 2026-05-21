# Gmail Intake Notes

## Connected Mailbox

The connected Gmail profile currently resolves to `ramorri2@gmail.com`, but the LA County source emails being inspected are addressed to `robert@civicexperiment.com` within that mailbox.

## Observed LA County Pattern

Observed from real mailbox samples on May 20, 2026:

- sender: `BOSEXEC@subscriptions.lacounty.gov`
- sender: `lacounty@subscriptions.lacounty.gov`
- delivery style: GovDelivery email
- attachments: none observed in the sampled agenda emails
- primary retrieval mode: links in the email body

## Message Types Seen

- `Agenda for the Board Meeting on ...`
- `Supplemental Agenda for the Board Meeting on ...`
- `Agenda Spotlight - ...`
- `Cluster Meeting Agendas - ...`

## Link Types Seen

- Board agenda page on `bos.lacounty.gov`
- direct PDFs on `file.lacounty.gov`
- live meeting page
- public comment page

## Implementation Direction

The first ingestion adapter should:

1. search Gmail for known sender and subject patterns
2. read message bodies
3. unwrap GovDelivery tracking links
4. classify board pages versus direct PDF links
5. download the relevant targets
6. store email metadata and normalized link records alongside documents
