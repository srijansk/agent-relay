```markdown
## Objective
The `/v1/orders?since=...` API endpoint incorrectly returns orders from the previous day when today's date is passed as the `since` parameter due to improper timezone handling.

## Root cause
The issue arises because the current code does not correctly handle timezone conversion when parsing the `since` date parameter. The server or database might operate in a different timezone than expected, causing the date comparison logic to inadvertently include orders from the previous day. This happens because the `since` parameter is interpreted as a date without considering the time component, leading to incorrect inclusions of orders that fall within the previous day's time range in UTC or another timezone.

## Change list
- **src/api/orders.py**: Modify the function responsible for parsing the `since` query parameter to include timezone information using the `pytz` library, ensuring accurate date comparisons.
- **src/utils/datetime.py**: If this file exists, review and update any date parsing or timezone handling functions to ensure they correctly manage timezones.

## Test plan
- **Failing Test**: Implement `test_orders_since_today` in the test suite to verify that the API endpoint `/v1/orders?since=<today's date>` only returns orders from today onwards. This test should initially fail, demonstrating the bug.
- **Regression Test**: Implement `test_orders_since_with_timezone` to verify the correct handling of the `since` parameter when the server operates in different timezones, ensuring consistent behavior regardless of the server's timezone setting.
- **Adjacent Code Paths**: Review and test any other date parsing or filtering functions in `src/api/orders.py` and `src/utils/datetime.py` to ensure they handle timezones correctly.

## Risk and rollback
- **Risks**: The primary risk is that changes to timezone handling might inadvertently affect other date-related functionalities if not thoroughly tested. There is also a risk of introducing new bugs if the timezone conversion logic is not implemented correctly.
- **Rollback**: Revert the changes by checking out the previous commit using its hash. Ensure that the commit hash is documented before making changes to facilitate easy rollback. If issues arise, revert to this commit and re-evaluate the approach to fixing the timezone handling.
```