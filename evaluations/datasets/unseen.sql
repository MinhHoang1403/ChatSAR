CREATE SCHEMA IF NOT EXISTS observatory_fixture;
CREATE TABLE observatory_fixture.readings (obs_code text, band text, exposure_seconds numeric, observed_on date);
INSERT INTO observatory_fixture.readings VALUES
('C0001','infrared',1.25,'2024-02-01'),('C0002','optical',0.75,'2024-02-29'),
('C0003','infrared',NULL,'2024-03-01'),('C0004','infrared',0.00,'2024-01-31');
CREATE SCHEMA IF NOT EXISTS recycling_fixture;
CREATE TABLE recycling_fixture.batches (batch_code text, material text, mass_kg numeric, recovered boolean, closed_at timestamptz);
INSERT INTO recycling_fixture.batches VALUES
('R1001','glass',2.50,true,'2026-12-01T00:00:00+07:00'),
('R1002','paper',1.50,false,'2026-12-31T23:59:59+07:00'),
('R1003','glass',1.50,false,'2027-01-01T00:00:00+07:00'),
('R1004','glass',NULL,false,'2026-11-30T23:59:59+07:00');
