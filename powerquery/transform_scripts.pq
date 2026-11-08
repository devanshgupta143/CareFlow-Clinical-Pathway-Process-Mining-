// Create a blank query named fxTransformClinicalEvents and paste this file.
// It returns a record containing [Transformed_Events] and
// [Rejected_Event_Rows]. Rejected timestamps are retained for audit rather
// than silently removed from the model refresh.
(Raw as table) as record =>
let
    PromotedHeaders =
        if List.Contains(Table.ColumnNames(Raw), "Column1") then
            Table.PromoteHeaders(Raw, [PromoteAllScalars = true])
        else
            Raw,

    TrimmedHeaders =
        Table.TransformColumnNames(
            PromotedHeaders,
            each Text.Trim(Text.Clean(_))
        ),

    RequiredColumns = {
        "case_id",
        "event_time",
        "stage",
        "department",
        "hospital",
        "patient_type",
        "wait_time_hours",
        "process_time_hours"
    },
    MissingColumns =
        List.Difference(RequiredColumns, Table.ColumnNames(TrimmedHeaders)),
    CheckedColumns =
        if List.Count(MissingColumns) > 0 then
            error Error.Record(
                "Schema.Error",
                "Required clinical event columns are missing.",
                MissingColumns
            )
        else
            TrimmedHeaders,

    TrimmedText =
        Table.TransformColumns(
            CheckedColumns,
            List.Transform(
                List.Intersect({RequiredColumns, Table.ColumnNames(CheckedColumns)}),
                (ColumnName) => {
                    ColumnName,
                    each if _ = null then null else Text.Trim(Text.Clean(Text.From(_))),
                    type nullable text
                }
            )
        ),

    WithSourceRow =
        Table.AddIndexColumn(TrimmedText, "Source_Row_Number", 1, 1, Int64.Type),
    WithParsedTimestamp =
        Table.AddColumn(
            WithSourceRow,
            "Timestamp",
            each
                let
                    RawTimestamp = [event_time],
                    RawTimestampText =
                        if RawTimestamp = null then null else Text.Trim(Text.From(RawTimestamp)),
                    HasExplicitZone =
                        RawTimestampText <> null
                            and (
                                Text.EndsWith(Text.Upper(RawTimestampText), "Z")
                                    or Text.PositionOfAny(
                                        Text.Range(RawTimestampText, 10),
                                        {"+", "-"}
                                    ) >= 0
                            )
                in
                    if RawTimestamp = null then null
                    else if HasExplicitZone then
                        (
                            try DateTimeZone.SwitchZone(
                                DateTimeZone.FromText(RawTimestampText),
                                0
                            )
                            otherwise null
                        )
                    else
                        (
                            try DateTimeZone.AddZone(
                                DateTime.FromText(RawTimestampText, [Culture = "en-US"]),
                                0
                            )
                            otherwise null
                        ),
            type nullable datetimezone
        ),
    WithTimestampStatus =
        Table.AddColumn(
            WithParsedTimestamp,
            "Timestamp_Quality",
            each if [Timestamp] = null then "Missing or invalid timestamp" else "Valid",
            type text
        ),
    ValidTimestampRows =
        Table.SelectRows(WithTimestampStatus, each [Timestamp] <> null),
    RejectedTimestampRows =
        Table.SelectRows(WithTimestampStatus, each [Timestamp] = null),

    WithCaseID =
        Table.AddColumn(
            ValidTimestampRows,
            "Case_ID",
            each Text.Trim(Text.From([case_id])),
            type text
        ),
    WithEventName =
        Table.AddColumn(
            WithCaseID,
            "Event_Name",
            each
                let
                    StageValue = Text.Lower(Text.Trim(Text.From([stage])))
                in
                    if StageValue = "admission" then "Admission"
                    else if StageValue = "diagnosis" then "Diagnosis"
                    else if StageValue = "treatment" then "Treatment"
                    else if StageValue = "discharge" then "Discharge"
                    else error Error.Record(
                        "Stage.Error",
                        "Stage is outside the approved clinical stage set.",
                        [Case_ID = [Case_ID], Stage = [stage]]
                    ),
            type text
        ),
    WithDepartment =
        Table.AddColumn(WithEventName, "Department", each [department], type nullable text),
    WithHospital =
        Table.AddColumn(WithDepartment, "Hospital", each [hospital], type nullable text),
    WithPatientType =
        Table.AddColumn(WithHospital, "Patient_Type", each [patient_type], type nullable text),
    WithWaitHours =
        Table.AddColumn(
            WithPatientType,
            "Wait_Time_Hours",
            each try Number.FromText([wait_time_hours], "en-US") otherwise null,
            type nullable number
        ),
    WithStageDuration =
        Table.AddColumn(
            WithWaitHours,
            "Stage_Duration_Hours",
            each try Number.FromText([process_time_hours], "en-US") otherwise null,
            type nullable number
        ),
    WithDurationStatus =
        Table.AddColumn(
            WithStageDuration,
            "Duration_Quality",
            each
                if [Stage_Duration_Hours] = null then "Missing or invalid duration"
                else if [Stage_Duration_Hours] < 0 then "Negative duration"
                else "Valid",
            type text
        ),
    ValidDurationRows =
        Table.SelectRows(WithDurationStatus, each [Duration_Quality] = "Valid"),
    RejectedDurationRows =
        Table.SelectRows(WithDurationStatus, each [Duration_Quality] <> "Valid"),
    WithDate =
        Table.AddColumn(
            ValidDurationRows,
            "Date",
            each Date.From(DateTimeZone.RemoveZone([Timestamp])),
            type date
        ),
    WithDateKey =
        Table.AddColumn(
            WithDate,
            "DateKey",
            each Date.Year([Date]) * 10000 + Date.Month([Date]) * 100 + Date.Day([Date]),
            Int64.Type
        ),
    WithDayName =
        Table.AddColumn(
            WithDateKey,
            "Day_Name",
            each Date.DayOfWeekName([Date], "en-US"),
            type text
        ),
    WithHour =
        Table.AddColumn(
            WithDayName,
            "Hour_of_Day",
            each Time.Hour(DateTime.Time(DateTimeZone.RemoveZone([Timestamp]))),
            Int64.Type
        ),
    WithDepartmentID =
        Table.AddColumn(
            WithHour,
            "Department_ID",
            each
                "DEPT-"
                    & Text.Upper(
                        Text.Start(
                            Binary.ToText(
                                Binary.Hash(
                                    Text.ToBinary(
                                        Text.Lower(Text.Trim([Department])),
                                        TextEncoding.Utf8
                                    ),
                                    CryptoAlgorithm.SHA256
                                ),
                                BinaryEncoding.Hex
                            ),
                            12
                        )
                    ),
            type text
        ),
    SortedEvents =
        Table.Sort(
            WithDepartmentID,
            {{"Case_ID", Order.Ascending}, {"Timestamp", Order.Ascending}}
        ),
    CycleByCase =
        Table.Group(
            SortedEvents,
            {"Case_ID"},
            {
                {
                    "Cycle_Time_Hours",
                    each
                        Duration.TotalHours(
                            List.Max(
                                List.Transform(
                                    Table.ToRecords(_),
                                    (Row) =>
                                        DateTimeZone.RemoveZone(Row[Timestamp])
                                            + #duration(
                                                0,
                                                0,
                                                0,
                                                Number.RoundDown(
                                                    Row[Stage_Duration_Hours] * 3600
                                                )
                                            )
                                )
                            )
                                - DateTimeZone.RemoveZone(List.Min([Timestamp]))
                        ),
                    type number
                }
            }
        ),
    JoinedCycle =
        Table.NestedJoin(
            SortedEvents,
            {"Case_ID"},
            CycleByCase,
            {"Case_ID"},
            "CaseCycle",
            JoinKind.LeftOuter
        ),
    ExpandedCycle =
        Table.ExpandTableColumn(JoinedCycle, "CaseCycle", {"Cycle_Time_Hours"}),
    WithCycleBucket =
        Table.AddColumn(
            ExpandedCycle,
            "Cycle_Time_Buckets",
            each
                if [Cycle_Time_Hours] = null then null
                else if [Cycle_Time_Hours] <= 6 then "0-6h"
                else if [Cycle_Time_Hours] <= 12 then "6-12h"
                else if [Cycle_Time_Hours] <= 18 then "12-18h"
                else if [Cycle_Time_Hours] <= 24 then "18-24h"
                else if [Cycle_Time_Hours] <= 30 then "24-30h"
                else ">30h",
            type nullable text
        ),
    FactColumns =
        Table.SelectColumns(
            WithCycleBucket,
            {
                "Case_ID",
                "Event_Name",
                "Timestamp",
                "Date",
                "DateKey",
                "Department_ID",
                "Department",
                "Hospital",
                "Patient_Type",
                "Wait_Time_Hours",
                "Stage_Duration_Hours",
                "Cycle_Time_Hours",
                "Cycle_Time_Buckets",
                "Day_Name",
                "Hour_of_Day",
                "Source_Row_Number"
            }
        ),
    DimDepartments =
        Table.AddColumn(
            Table.Distinct(
                Table.SelectColumns(FactColumns, {"Department_ID", "Department"})
            ),
            "Cost_Center",
            each null,
            type nullable text
        ),
    CalendarStart = List.Min(FactColumns[Date]),
    CalendarEnd = List.Max(FactColumns[Date]),
    CalendarLength = Duration.Days(CalendarEnd - CalendarStart) + 1,
    CalendarDates = List.Dates(CalendarStart, CalendarLength, #duration(1, 0, 0, 0)),
    CalendarTable =
        Table.TransformColumnTypes(
            Table.FromList(
                CalendarDates,
                Splitter.SplitByNothing(),
                {"Date"},
                null,
                ExtraValues.Error
            ),
            {{"Date", type date}}
        ),
    DimDateWithKey =
        Table.AddColumn(
            CalendarTable,
            "DateKey",
            each Date.Year([Date]) * 10000 + Date.Month([Date]) * 100 + Date.Day([Date]),
            Int64.Type
        ),
    DimDateWithYear =
        Table.AddColumn(DimDateWithKey, "Year", each Date.Year([Date]), Int64.Type),
    DimDateWithQuarter =
        Table.AddColumn(
            DimDateWithYear,
            "Quarter",
            each "Q" & Text.From(Date.QuarterOfYear([Date])),
            type text
        ),
    DimDateWithMonth =
        Table.AddColumn(
            DimDateWithQuarter,
            "Month",
            each Date.MonthName([Date], "en-US"),
            type text
        ),
    DimDateWithMonthNumber =
        Table.AddColumn(
            DimDateWithMonth,
            "MonthNumber",
            each Date.Month([Date]),
            Int64.Type
        ),
    DimDateWithWeekday =
        Table.AddColumn(
            DimDateWithMonthNumber,
            "Weekday",
            each Date.DayOfWeekName([Date], "en-US"),
            type text
        ),
    DimDateWithWeekdayNumber =
        Table.AddColumn(
            DimDateWithWeekday,
            "WeekdayNumber",
            each Date.DayOfWeek([Date], Day.Monday) + 1,
            Int64.Type
        ),
    DimDate =
        Table.AddColumn(
            DimDateWithWeekdayNumber,
            "Is_Weekend",
            each Date.DayOfWeek([Date], Day.Monday) >= 5,
            type logical
        )
in
    [
        Transformed_Events = FactColumns,
        Dim_Departments = DimDepartments,
        Dim_Date = DimDate,
        Rejected_Event_Rows = RejectedTimestampRows,
        Rejected_Duration_Rows = RejectedDurationRows
    ]
