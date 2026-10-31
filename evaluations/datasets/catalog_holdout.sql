CREATE SCHEMA IF NOT EXISTS museum_fixture;
CREATE TABLE museum_fixture.objects (asset_tag text,gallery text,mass_g numeric,on_display boolean,cataloged_on date);
INSERT INTO museum_fixture.objects VALUES
('0019','modern',0.35,false,'2028-02-01'),('0028','modern',1.65,true,'2028-02-29'),
('0104','archive',NULL,false,'2028-03-01'),('0305','modern',0.00,false,'2028-01-31');
CREATE SCHEMA IF NOT EXISTS waterworks_fixture;
CREATE TABLE waterworks_fixture.flow_checks (check_code text,zone text,volume_l numeric,inspected boolean,read_at timestamptz);
INSERT INTO waterworks_fixture.flow_checks VALUES
('W1001','ridge',0.18,false,'2027-01-31T23:59:59+07:00'),
('W1002','ridge',2.04,true,'2027-02-01T00:00:00+07:00'),
('W1003','ridge',0.27,false,'2027-02-28T23:59:59+07:00'),
('W1004','ridge',NULL,false,'2027-03-01T00:00:00+07:00'),
('W1005','canal',0.91,false,'2027-01-31T23:59:59+07:00');
