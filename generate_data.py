import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

np.random.seed(42)
num_records = 12482

patient_ids = [f"PT-{i:05d}" for i in range(10001, 10001 + num_records)]
hospitals = ["City General Hospital", "St. Jude Medical Center", "Metro Healthcare"]
departments = ["General Medicine", "Surgery", "Orthopedics", "Cardiology", "Gynecology", "Others"]
patient_types = ["Inpatient", "Outpatient"]

hospital_choices = np.random.choice(hospitals, size=num_records, p=[0.4, 0.35, 0.25])
dept_choices = np.random.choice(departments, size=num_records, p=[0.28, 0.22, 0.16, 0.12, 0.09, 0.13])
type_choices = np.random.choice(patient_types, size=num_records, p=[0.7, 0.3])

start_date = datetime(2025, 1, 1)
end_date = datetime(2025, 9, 30)
date_range = (end_date - start_date).days

admission_dates = [
    start_date + timedelta(days=np.random.randint(0, date_range), hours=np.random.randint(0, 24), minutes=np.random.randint(0, 60))
    for _ in range(num_records)
]

admission_wait = np.random.uniform(0.5, 4.0, size=num_records)
diagnosis_wait = np.random.uniform(1.0, 8.0, size=num_records)
treatment_wait = np.random.uniform(2.0, 15.0, size=num_records)
discharge_wait = np.random.uniform(1.0, 8.0, size=num_records)

length_of_stay = (admission_wait + diagnosis_wait + treatment_wait + discharge_wait) / 24.0 + np.random.exponential(scale=2.0, size=num_records)
readmission = np.random.choice([0, 1], size=num_records, p=[0.937, 0.063])

df = pd.DataFrame({
    'patient_id': patient_ids,
    'hospital_name': hospital_choices,
    'department': dept_choices,
    'patient_type': type_choices,
    'admission_timestamp': admission_dates,
    'admission_duration_hours': np.round(admission_wait, 2),
    'diagnosis_duration_hours': np.round(diagnosis_wait, 2),
    'treatment_duration_hours': np.round(treatment_wait, 2),
    'discharge_duration_hours': np.round(discharge_wait, 2),
    'length_of_stay_days': np.round(length_of_stay, 2),
    'readmission_flag': readmission
})

os.makedirs('data/raw', exist_ok=True)
df.to_csv('data/raw/careflow_patient_logs.csv', index=False)
print("Dataset generated successfully at data/raw/careflow_patient_logs.csv!")