# EduQuest staging test report

**Date:** 1 October 2026\
**Target:** `https://eduquesttutors.co.za/staging/`\
**Method:** Manual, read-only browser testing in Chrome at desktop viewport\
**Accounts tested:** Admin, tutor, learner

## Summary

All three supplied accounts signed in successfully and reached their expected role dashboards. The main dashboards and representative read-only pages loaded. Two user-facing defects were reproduced: the learner class page labels a Saturday class as today's Thursday class, and one quiz attempt is shown with a 1 January 1970 timestamp. A past-due quiz is also listed under Active Quizzes while unavailable.

No records were created, edited, deleted, or submitted. Attendance was not marked, quizzes were not attempted, and external meeting links were not opened.

## Findings

### EQ-01 — Learner class page shows the wrong class as today's class

**Severity:** High\
**Area:** Learner → My Classes\
**Page:** `/staging/learner/classes.php`

On Thursday, 1 October 2026, the page showed “Today's Class — Thursday — 17:00.” Its own Weekly Schedule showed the class on Saturday at 17:00. The learner dashboard also showed Saturday at 17:00, matching the tutor's class timetable.

This can mislead a learner into joining or marking attendance for the wrong day. The attendance/join action was not clicked.

**Suggested fix:** Derive the “Today's Class” card from the scheduled class's actual weekday and date, and show an empty state when no class is scheduled today.

### EQ-02 — Quiz history displays an epoch date

**Severity:** Medium\
**Area:** Learner → Quiz History and tutor → Learner Profile\
**Page:** `/staging/learner/quiz_history.php`

The `test 1 maths` attempt appears as **1 January 1970, 02:00**, with a 0% score and 0 minutes taken. The same attempt date appears on the tutor's learner profile. This looks like a missing or invalid attempt timestamp being rendered as the Unix epoch.

**Suggested fix:** Check the stored attempt timestamp and handle absent/invalid dates explicitly instead of formatting them as a real date.

### EQ-03 — Past-due quiz appears active but cannot be opened

**Severity:** Medium\
**Area:** Learner → My Quizzes\
**Page:** `/staging/learner/my_quizzes.php`

`test 1 maths` appears under **Active Quizzes**, but its due date is 3 August 2026, the page says **Past due date**, and the action is **Not Available**. The learner history also shows Attempt 1/1 and provides a retake link, so the intended retake policy is unclear.

**Suggested fix:** Clarify the quiz's state and retake rules. Move expired quizzes to a closed/past-due section or explain why they remain active, and keep the available action consistent across quiz list and history.

### EQ-04 — Parent-to-learner relationship is missing in staging data

**Severity:** Test-data gap\
**Area:** Admin and tutor user management

The admin account shows one parent and one learner, but the parent has **0 children** and the learner has **0 linked parents**. Consequently, the parent portal and parent-visible learner journey could not be tested. No parent login was supplied.

**Suggested fix:** Link the staging parent account to the staging learner and provide a parent test login for a follow-up pass.

### EQ-05 — Billing rates need clarification before billing-flow testing

**Severity:** Needs product confirmation\
**Area:** Tutor attendance / learner pricing

The tutor attendance form showed **R250/hour**, while the tutor's learner profile showed **R150/class**. There are no attendance or invoice records in this staging dataset, so I could not verify whether these are intentionally separate rates or a billing mismatch.

**Suggested follow-up:** Confirm the pricing rule, then test one clearly marked staging attendance/invoice flow with disposable data.

## Coverage

| Role | Login | Pages inspected |
|---|---|---|
| Admin | Passed | Dashboard, tenant management, tutor list/profile, learner list, parent list, school management |
| Tutor | Passed | Dashboard, learner list/profile, timetable, attendance, test marks, parent management |
| Learner | Passed | Dashboard, classes, materials, modules, quizzes, quiz history/results, upcoming tests, performance analytics, attendance |
| Parent | Not tested | No parent credentials were supplied |

## Staging data observed

- One tenant, one active tutor, one learner, one parent, no schools, no active subscriptions, and no payment/revenue records.
- No learner attendance, test-mark, material, or module records were available.
- The tutor dashboard had one pending lesson request. It was left unchanged.
- The learner had one completed quiz with a valid August 2026 result and one zero-duration attempt with the epoch date above.

## Limits

This was a manual desktop functional/UI pass. It did not include a load test, mobile/responsive checks, automated accessibility checks, authorization-boundary probing, or write workflows such as attendance, quiz submission, billing, or parent linking. Performance improvement cannot be concluded from this run.
