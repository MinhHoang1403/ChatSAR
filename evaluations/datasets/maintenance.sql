-- Schema mới chỉ dùng cho evaluation, không nhập vào prompt phát triển.
CREATE TABLE oracle_fixture.work_orders (
 work_order TEXT PRIMARY KEY, asset_code TEXT NOT NULL,
 labor_hours NUMERIC(18,2), state TEXT NOT NULL
);
INSERT INTO oracle_fixture.work_orders VALUES
('W01','0007',1.10,'completed'),('W02','0007',1.20,'waiting'),
('W03','0008',0.20,'completed'),('W04','0012',NULL,'waiting');
