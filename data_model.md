# Star Schema Data Model Architecture

> The enterprise PBIP table schema and build steps for
> `Fact_Clinical_Events`, `Dim_Patients`, `Dim_Departments`, and `Dim_Date`
> are maintained in
> [docs/enterprise_power_bi_implementation.md](docs/enterprise_power_bi_implementation.md).
> That document reflects source availability and the optional patient-ID map.

## Model Overview

- **Architecture Type**: Star schema with a case-grain hub and event/transition facts.
- **Facts**: `Cases` (one row per encounter), `Events`, `Transitions`,
  `StageMetrics`, `Bottlenecks`, `VariantFrequency`, and `VariantFlows`.
- **Dimensions**: `DimDate`, `DimActivity`, `DimDepartment`, `DimDiagnosis`,
  `DimResource`, and `DimVariant`.

## Generated Power BI model

The PM4Py exporter now defines the concrete `Cases`, `Events`, `Transitions`,
stage/bottleneck, variant-flow and dimension table schemas. See
[docs/power_bi_integration.md](docs/power_bi_integration.md) for field-level
definitions, relationship cardinalities, DAX measures, and PBIP import steps.
