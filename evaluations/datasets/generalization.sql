CREATE SCHEMA recovery_oracle;
CREATE TABLE recovery_oracle.pieces(piece_ref TEXT,wing TEXT,insured_value NUMERIC,catalogued BOOLEAN,received_on DATE);
INSERT INTO recovery_oracle.pieces VALUES
('A0009','east',0.10,false,'2026-08-31'),('A0010','east',0.20,true,'2026-09-01'),
('A0101','west',-0.05,false,'2026-09-30'),('A0200','west',NULL,true,'2026-10-01');
CREATE TABLE recovery_oracle.batches(batch_ref TEXT,oven TEXT,flour_kg NUMERIC,baked_at TIMESTAMPTZ);
INSERT INTO recovery_oracle.batches VALUES
('0038','kiln-A',1.25,'2026-08-31T17:00:00Z'),('0081','kiln-B',2.75,'2026-09-20T10:00:00Z'),
('0099','kiln-A',NULL,'2026-09-30T17:00:00Z'),('0450','kiln-B',-0.50,'2026-08-31T16:59:59Z');
