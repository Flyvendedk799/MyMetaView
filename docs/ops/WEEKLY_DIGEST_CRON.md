# Weekly Performance Digest Scheduling

MyMetaView sends a weekly performance digest email to each account with at least one verified domain every Monday.
This document explains how to trigger and schedule the digest job via external cron, ServerHoster, or Railway.

---

## Endpoint Details

- **Method**: `POST`
- **Path**: `/api/v1/jobs/weekly-digest`
- **Authentication**: Shared secret configured via environment variable `CRON_SECRET` or `WEEKLY_DIGEST_SECRET` (returns 401 if unconfigured).
  Supplied via one of:
  - Header `X-Cron-Secret: <secret>`
  - Header `X-Weekly-Digest-Secret: <secret>`
  - Header `Authorization: Bearer <secret>`

### Parameters

| Parameter | Type | In | Description |
|-----------|------|----|-------------|
| `dry_run` | bool | Query / JSON body | When `true`, calculates and returns the digest payload without sending emails or recording duplicate-send records. Default `false`. |
| `as_of_date` | string (YYYY-MM-DD) | Query / JSON body | Optional reference date (defaults to UTC today). Used to test specific time windows. |

---

## Scheduling Options

### 1. External Cron (Linux crontab)

To schedule the digest to run every Monday at 08:00 UTC:

```bash
0 8 * * 1 curl -s -X POST "https://api.mymetaview.com/api/v1/jobs/weekly-digest" \
  -H "X-Cron-Secret: ${CRON_SECRET}" \
  -H "Content-Type: application/json" > /dev/null 2>&1
```

### 2. ServerHoster / Cron-Job.org / External Scheduler

Configure a recurring HTTP monitor/webhook:
- **URL**: `https://api.mymetaview.com/api/v1/jobs/weekly-digest`
- **HTTP Method**: `POST`
- **Schedule**: Every Monday at `08:00 UTC` (`0 8 * * 1`)
- **Headers**:
  ```http
  X-Cron-Secret: <YOUR_CRON_SECRET>
  Content-Type: application/json
  ```
- **Expected Status**: `202 Accepted` for a live run (the digest is queued on the `bulk_generation` worker). `200 OK` for `dry_run=true`, which returns the payload in the response.

### 3. Railway Cron Service / Worker

In Railway:
1. Add a scheduled job or cron trigger with schedule `0 8 * * 1`.
2. Set command:
   ```bash
   curl -f -X POST "http://localhost:8000/api/v1/jobs/weekly-digest" -H "X-Cron-Secret: $CRON_SECRET"
   ```

---

## Testing / Dry Run

To test what would be sent without actually delivering emails or committing send markers:

```bash
curl -X POST "https://api.mymetaview.com/api/v1/jobs/weekly-digest?dry_run=true" \
  -H "X-Cron-Secret: <YOUR_CRON_SECRET>"
```

Response JSON:
```json
{
  "as_of_date": "2026-11-02",
  "iso_year": 2026,
  "iso_week": 45,
  "dry_run": true,
  "period": {
    "current_7d": "2026-10-26 to 2026-11-01",
    "previous_7d": "2026-10-19 to 2026-10-25"
  },
  "total_users_checked": 10,
  "sent_count": 0,
  "would_send_count": 8,
  "skipped_count": 2,
  "failed_count": 0,
  "would_send": [ ... ],
  "skipped": [
    { "user_id": 2, "email": "optedout@example.com", "reason": "opted_out" },
    { "user_id": 5, "email": "inactive@example.com", "reason": "zero_impressions" }
  ]
}
```

---

## Live runs

A live trigger returns immediately:

```json
{
  "queued": true,
  "job_id": "rq-job-id",
  "dry_run": false,
  "as_of_date": null
}
```

The web worker does not send mail itself. `python -m backend.queue.worker` must be running (it already is on the deployed start command) so the `bulk_generation` queue can deliver the batch. The job timeout is 60 minutes, independent of the web worker timeout. If the queue is unavailable the trigger returns `503` and nothing is sent.

---

## Safety & Deduplication

- **Duplicate-send guard**: The send row is inserted before delivery, and the unique `(user, ISO week)` constraint is what stops a second worker. Running the trigger again in the same ISO week sends nothing more.
- **Failed delivery**: If sending fails, that claim is removed so a later run can retry. A delivery that succeeded is not sent again.
- **Opt-out**: Accounts with the "Weekly performance email" toggle disabled or unsubscribed via the email link are automatically skipped.
- **Zero-activity filter**: Accounts with zero impressions across both 7-day windows receive no email.
- **Error isolation**: A failed delivery for one account is logged and does not abort processing for other accounts.
- **Organization access**: An organization domain is included only for users who currently own or belong to that organization. The user who created the domain stops receiving it after they leave. Domains with no organization still go to the user who created them.
