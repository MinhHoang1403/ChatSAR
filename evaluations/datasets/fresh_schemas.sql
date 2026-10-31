CREATE SCHEMA IF NOT EXISTS ceramics_fixture;
CREATE TABLE ceramics_fixture.firings (kiln_tag text, glaze text, weight_g numeric, ready boolean, fired_on date);
INSERT INTO ceramics_fixture.firings VALUES
('0004','teal',2.40,false,'2024-02-01'),('0015','teal',0.60,true,'2024-02-29'),
('0200','amber',NULL,false,'2024-03-01'),('0300','teal',0.00,false,'2024-01-31');
CREATE SCHEMA IF NOT EXISTS marine_fixture;
CREATE TABLE marine_fixture.samples (station_code text, sector text, depth_m numeric, calibrated boolean, logged_at timestamptz);
INSERT INTO marine_fixture.samples VALUES
('B0001','east',1.20,false,'2026-12-01T00:00:00+07:00'),
('B0002','east',2.30,true,'2026-12-31T23:59:59+07:00'),
('B0003','east',NULL,false,'2027-01-01T00:00:00+07:00'),
('B0004','east',0.80,false,'2026-11-30T23:59:59+07:00'),
('B0005','west',5.00,false,'2027-02-01T00:00:00+07:00');
