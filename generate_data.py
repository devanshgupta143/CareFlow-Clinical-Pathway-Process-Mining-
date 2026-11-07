import csv
import random
import datetime

# Ensure reproducible data generation
random.seed(42)

hospitals = ['City General Hospital', 'St. Jude Medical Center', 'Metro Health Institute']
departments = ['General Medicine', 'Surgery', 'Orthopedics', 'Cardiology', 'Gynecology', 'Others']
patient_types = ['Inpatient', 'Outpatient', 'Emergency']
diagnoses = ['Respiratory Infection', 'Fracture', 'Cardiovascular', 'Diabetes', 'Gastrointestinal']
delayed_reasons = ['Waiting for test results', 'Bed availability', 'Medication delay', 'Patient refusal', 'None']

acts = ['Admission', 'Diagnosis', 'Treatment', 'Discharge']
stage_mapping = {
    'Admission': 'Admission',
    'Diagnosis': 'Diagnosis',
    'Treatment': 'Treatment',
    'Discharge': 'Discharge'
}

names = ['Ravi Kumar', 'Meena Sharma', 'Arjun Patel', 'Priya Singh',
         'Ahmed Khan', 'Sneha Reddy', 'Vikram Joshi', 'Anita Desai',
         'Rahul Verma', 'Kavita Nair', 'Suresh Iyer', 'Pooja Gupta',
         'Manish Rao', 'Deepa Menon', 'Ajay Kulkarni', 'Neha Bose',
         'Rohit Malhotra', 'Sonia Chatterjee', 'Kiran Pillai', 'Amit Trivedi']

event_rows = [[
    'case_id', 'patient_name', 'hospital', 'department', 'patient_type', 
    'primary_diagnosis', 'event_activity', 'event_time', 'stage', 
    'wait_time_hours', 'process_time_hours'
]]

metadata_rows = [[
    'case_id', 'total_length_of_stay_days', 'total_process_time_hours', 
    'is_readmitted', 'patient_satisfaction_pct', 'delayed_discharge_reason'
]]

# Generate 2,500 comprehensive patient cases spanning Jan 1 to Sep 30, 2025
for i in range(1, 2501):
    case_id = f'P{str(i).zfill(4)}'
    patient = random.choice(names)
    hospital = random.choice(hospitals)
    dept = random.choice(departments)
    ptype = random.choice(patient_types)
    diag = random.choice(diagnoses)
    
    # Case metadata matching target benchmarks (~4.2 days LOS, ~18.6h process time, ~6.3% readmission, ~92% satisfaction)
    los_days = round(random.uniform(1.0, 8.5), 1)
    proc_time = round(random.uniform(12.0, 24.0), 1)
    is_readm = 1 if random.random() < 0.063 else 0
    satisfaction = random.randint(85, 100)
    delay_reason = random.choices(
        delayed_reasons, 
        weights=[32, 24, 18, 12, 14], 
        k=1
    )[0]
    
    metadata_rows.append([case_id, los_days, proc_time, is_readm, satisfaction, delay_reason])
    
    # Generate sequential event log timestamps
    start = datetime.datetime(2025, 1, 1) + datetime.timedelta(days=random.randint(0, 270))
    for a in acts:
        start += datetime.timedelta(hours=random.randint(2, 5), minutes=random.choice([0, 15, 30]))
        wait_h = round(random.uniform(0.5, 3.0), 1)
        dur_h = round(random.uniform(1.5, 4.5), 1)
        event_rows.append([
            case_id, patient, hospital, dept, ptype, diag, 
            a, start.strftime('%Y-%m-%d %H:%M:%S'), stage_mapping[a], wait_h, dur_h
        ])

# Write out clinical_events.csv
with open('clinical_events.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(event_rows)

# Write out case_metadata.csv
with open('case_metadata.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(metadata_rows)

print(f'Successfully generated files!')
print(f' - clinical_events.csv: {len(event_rows) - 1} rows')
print(f' - case_metadata.csv: {len(metadata_rows) - 1} rows')