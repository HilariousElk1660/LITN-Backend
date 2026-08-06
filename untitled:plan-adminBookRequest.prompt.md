Goal: update the admin book request workflow in the UI and add a per-book report action.

1. Identify admin upload book view and request tabs
   - locate frontend component(s) rendering admin upload book page
   - confirm paid/declined tab implementation and request action buttons
   - locate backend endpoints used by accept/decline actions

2. Remove decline and accept buttons from the paid tab
   - modify paid-tab render logic so accepted/declined actions are not shown there
   - preserve status display only for paid requests

3. Add confirmation prompt when accepting
   - add client-side confirmation dialog before calling accept endpoint
   - text: "Are you sure you want to accept this book request?"
   - only continue when confirmed

4. Add decline modal for declining a book request
   - add a modal component triggered by Decline button
   - modal content:
     - heading: "Are you sure you want to decline?"
     - textarea for decline reason
     - confirm and cancel buttons
   - require a non-empty reason before submitting
   - submit decline action with reason payload

5. Remove declined button under declined tab
   - update declined-tab render logic to hide any action buttons
   - keep declined status summary only

6. Generate report button on admin upload book view
   - add a per-book "Generate Report" button in admin book list / upload page
   - clicking it should fetch or compute the report for that book
   - report fields:
     - number of book requests
     - number of book requests accepted
     - number of book requests declined
     - number of readers done with book
     - number of readers currently reading
   - display report in a modal or inline panel
    - add an export as a xslx button


7. Backend support and data sources
   - determine if existing admin book request and reader progress endpoints already provide counts
   - add or extend endpoint to return report counts per book if needed
   - include decline reason storage if not already present
   - ensure decline endpoint records reason and status
   - add decline reason to email being sent

8. Verification and testing
   - verify tab button removal and UI state handling
   - verify accept confirmation prompt works
   - verify decline modal opens, collects reason, and submits decline
   - verify report button returns expected counts
   - test admin workflow end-to-end in the app
