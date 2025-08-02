-- Database setup script for Doctor AI WhatsApp Assistant
-- Run this script in your Supabase SQL editor

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Patients table (REVISED SCHEMA)
CREATE TABLE IF NOT EXISTS patients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number TEXT NOT NULL UNIQUE,
    full_name TEXT,
    email TEXT,
    age INT,
    gender TEXT,
    notes TEXT, -- Used for temporary booking context
    onboarding_step TEXT DEFAULT 'start',
    onboarding_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Doctor availability table
CREATE TABLE IF NOT EXISTS doctor_availability (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slot_start_time TIMESTAMPTZ NOT NULL,
    slot_end_time TIMESTAMPTZ NOT NULL,
    is_booked BOOLEAN DEFAULT FALSE,
    doctor_name TEXT DEFAULT 'Dr. Sunil Mishra',
    doctor_id TEXT DEFAULT 'dr_sunil_mishra_001',
    slot_type TEXT DEFAULT 'consultation', -- consultation, follow_up, emergency
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Appointments table
CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID REFERENCES patients(id) ON DELETE CASCADE,
    availability_id UUID REFERENCES doctor_availability(id) ON DELETE CASCADE,
    appointment_time TIMESTAMPTZ NOT NULL,
    status TEXT DEFAULT 'confirmed', -- confirmed, cancelled, completed, no_show
    google_calendar_event_id TEXT,
    notes TEXT,
    appointment_type TEXT DEFAULT 'consultation',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_patients_phone ON patients(phone_number);
CREATE INDEX IF NOT EXISTS idx_availability_slot_start ON doctor_availability(slot_start_time);
CREATE INDEX IF NOT EXISTS idx_availability_is_booked ON doctor_availability(is_booked);
CREATE INDEX IF NOT EXISTS idx_appointments_patient_id ON appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_appointment_time ON appointments(appointment_time);
CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status);

-- Add RLS (Row Level Security) policies if needed
-- ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE doctor_availability ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_patients_updated_at BEFORE UPDATE ON patients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_availability_updated_at BEFORE UPDATE ON doctor_availability
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_appointments_updated_at BEFORE UPDATE ON appointments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Seed some initial availability slots for testing
-- Insert slots for the next 7 days (Monday to Friday, 9 AM to 5 PM, 30-minute slots)

INSERT INTO doctor_availability (slot_start_time, slot_end_time, doctor_name, slot_type) VALUES
-- August 1, 2024 (Thursday)
('2024-08-01 13:00:00+00', '2024-08-01 13:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-01 13:30:00+00', '2024-08-01 14:00:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-01 14:00:00+00', '2024-08-01 14:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-01 14:30:00+00', '2024-08-01 15:00:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-01 15:00:00+00', '2024-08-01 15:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-01 15:30:00+00', '2024-08-01 16:00:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-01 16:00:00+00', '2024-08-01 16:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-01 16:30:00+00', '2024-08-01 17:00:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-01 17:00:00+00', '2024-08-01 17:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-01 17:30:00+00', '2024-08-01 18:00:00+00', 'Dr. Sunil Mishra', 'consultation'),

-- August 2, 2024 (Friday)
('2024-08-02 13:00:00+00', '2024-08-02 13:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-02 13:30:00+00', '2024-08-02 14:00:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-02 14:00:00+00', '2024-08-02 14:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-02 14:30:00+00', '2024-08-02 15:00:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-02 15:00:00+00', '2024-08-02 15:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-02 15:30:00+00', '2024-08-02 16:00:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-02 16:00:00+00', '2024-08-02 16:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-02 16:30:00+00', '2024-08-02 17:00:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-02 17:00:00+00', '2024-08-02 17:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-02 17:30:00+00', '2024-08-02 18:00:00+00', 'Dr. Sunil Mishra', 'consultation'),

-- August 5, 2024 (Monday)
('2024-08-05 13:00:00+00', '2024-08-05 13:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-05 13:30:00+00', '2024-08-05 14:00:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-05 14:00:00+00', '2024-08-05 14:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-05 14:30:00+00', '2024-08-05 15:00:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-05 15:00:00+00', '2024-08-05 15:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-05 15:30:00+00', '2024-08-05 16:00:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-05 16:00:00+00', '2024-08-05 16:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-05 16:30:00+00', '2024-08-05 17:00:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-05 17:00:00+00', '2024-08-05 17:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-05 17:30:00+00', '2024-08-05 18:00:00+00', 'Dr. Sunil Mishra', 'consultation'),

-- August 6, 2024 (Tuesday)
('2024-08-06 13:00:00+00', '2024-08-06 13:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-06 13:30:00+00', '2024-08-06 14:00:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-06 14:00:00+00', '2024-08-06 14:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-06 14:30:00+00', '2024-08-06 15:00:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-06 15:00:00+00', '2024-08-06 15:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-06 15:30:00+00', '2024-08-06 16:00:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-06 16:00:00+00', '2024-08-06 16:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-06 16:30:00+00', '2024-08-06 17:00:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-06 17:00:00+00', '2024-08-06 17:30:00+00', 'Dr. Sunil Mishra', 'consultation'),
('2024-08-06 17:30:00+00', '2024-08-06 18:00:00+00', 'Dr. Sunil Mishra', 'consultation');

-- Create a view for available slots (convenient for queries)
CREATE OR REPLACE VIEW available_slots AS
SELECT 
    id,
    slot_start_time,
    slot_end_time,
    doctor_name,
    slot_type,
    EXTRACT(DOW FROM slot_start_time) as day_of_week,
    TO_CHAR(slot_start_time, 'Day, Month DD at HH12:MI AM') as formatted_time
FROM doctor_availability 
WHERE is_booked = FALSE 
  AND slot_start_time > NOW()
ORDER BY slot_start_time;

-- Create a function to get available slots for a specific date range
CREATE OR REPLACE FUNCTION get_available_slots_for_date_range(
    start_date TIMESTAMPTZ DEFAULT NOW(),
    end_date TIMESTAMPTZ DEFAULT NOW() + INTERVAL '30 days'
)
RETURNS TABLE (
    id UUID,
    slot_start_time TIMESTAMPTZ,
    slot_end_time TIMESTAMPTZ,
    doctor_name TEXT,
    slot_type TEXT,
    formatted_time TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        da.id,
        da.slot_start_time,
        da.slot_end_time,
        da.doctor_name,
        da.slot_type,
        TO_CHAR(da.slot_start_time, 'Day, Month DD at HH12:MI AM') as formatted_time
    FROM doctor_availability da
    WHERE da.is_booked = FALSE 
      AND da.slot_start_time >= start_date
      AND da.slot_start_time <= end_date
    ORDER BY da.slot_start_time;
END;
$$ LANGUAGE plpgsql;

-- Create a function to book a slot (with transaction safety)
CREATE OR REPLACE FUNCTION book_appointment_slot(
    p_slot_id UUID,
    p_patient_id UUID
)
RETURNS UUID AS $$
DECLARE
    appointment_id UUID;
    slot_start TIMESTAMPTZ;
BEGIN
    -- Check if slot is still available and get start time
    SELECT slot_start_time INTO slot_start
    FROM doctor_availability 
    WHERE id = p_slot_id AND is_booked = FALSE;
    
    IF slot_start IS NULL THEN
        RAISE EXCEPTION 'Slot not available or does not exist';
    END IF;
    
    -- Mark slot as booked
    UPDATE doctor_availability 
    SET is_booked = TRUE, updated_at = NOW()
    WHERE id = p_slot_id AND is_booked = FALSE;
    
    -- Check if update was successful
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Failed to book slot - may have been booked by another user';
    END IF;
    
    -- Create appointment record
    INSERT INTO appointments (patient_id, availability_id, appointment_time, status)
    VALUES (p_patient_id, p_slot_id, slot_start, 'confirmed')
    RETURNING id INTO appointment_id;
    
    RETURN appointment_id;
END;
$$ LANGUAGE plpgsql;

-- Insert some test patients (optional - for testing)
-- INSERT INTO patients (phone_number, full_name) VALUES 
-- ('+1234567890', 'Test Patient 1'),
-- ('+1987654321', 'Test Patient 2');

-- Display summary
SELECT 'Database setup completed successfully!' as message;
SELECT COUNT(*) as total_available_slots FROM doctor_availability WHERE is_booked = FALSE;
SELECT COUNT(*) as total_patients FROM patients;
SELECT COUNT(*) as total_appointments FROM appointments; 