# Power Query (M-Code) Data Transformation Plan

## Step-by-Step Transformations
1. **Source Loading**: Connect to raw BigQuery view / CSV export.
2. **Data Type Casting**: Cast Patient_ID to Text, WaitTimeMinutes to Whole Number, and Timestamps to DateTimeZone.
3. **Time Zone Normalization**: Convert UTC event timestamps to local hospital timezone (EST/IST).
4. **Calculated Columns**:
   - Add `WaitTimeHours` = WaitTimeMinutes / 60
   - Add `Is_Bottleneck` = if WaitTimeMinutes > 60 then 1 else 0
# Enterprise fact transformations are implemented in
# [powerquery/transform_scripts.pq](powerquery/transform_scripts.pq), with
# invocation and rejected-timestamp handling documented in
# [docs/enterprise_power_bi_implementation.md](docs/enterprise_power_bi_implementation.md).
