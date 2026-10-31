-- Dữ liệu hoàn toàn tổng hợp; chỉ nạp trong transaction của oracle harness.
CREATE SCHEMA oracle_fixture;
CREATE TABLE oracle_fixture.shipments (
    shipment_code TEXT PRIMARY KEY,
    district TEXT NOT NULL,
    shipped_at TIMESTAMPTZ NOT NULL,
    fee NUMERIC(18, 2),
    delivery_status TEXT
);
INSERT INTO oracle_fixture.shipments VALUES
('0007', 'quận 3', '2026-09-01T00:00:00Z', 10.10, 'delivered'),
('0012', '3', '2026-09-30T17:00:00Z', 20.20, NULL),
('0100', 'quận 3', '2026-09-30T16:59:59Z', NULL, 'pending'),
('0101', 'quận 1', '2026-08-31T17:00:00Z', 0.00, 'delivered'),
('0102', 'quận 3', '2026-10-01T00:00:00Z', -0.10, 'delivered');

CREATE TABLE oracle_fixture.stays (
    booking_ref TEXT PRIMARY KEY,
    room_type TEXT NOT NULL,
    nights INTEGER NOT NULL,
    room_charge NUMERIC(18, 2),
    checked_in DATE NOT NULL
);
INSERT INTO oracle_fixture.stays VALUES
('H01', 'standard', 2, 100.05, '2026-09-01'),
('H02', 'suite', 1, 200.10, '2026-09-15'),
('H03', 'standard', 0, NULL, '2026-09-30'),
('H04', 'suite', 3, 0.00, '2026-10-01');

CREATE TABLE oracle_fixture.meters (
    meter_code TEXT PRIMARY KEY, zone TEXT NOT NULL,
    consumption NUMERIC(18, 3), reading_day DATE NOT NULL
);
INSERT INTO oracle_fixture.meters VALUES
('E01', 'north', 0.100, '2026-09-01'),
('E02', 'north', 0.200, '2026-09-02'),
('E03', 'south', NULL, '2026-09-03');

CREATE TABLE oracle_fixture.harvests (
    plot_code TEXT PRIMARY KEY, crop TEXT NOT NULL,
    yield_kg NUMERIC(18, 2), harvested BOOLEAN NOT NULL
);
INSERT INTO oracle_fixture.harvests VALUES
('A01', 'rice', 12.50, TRUE),
('A02', 'rice', 0.00, FALSE),
('A03', 'corn', NULL, FALSE);

-- Domain giữ riêng để đánh giá sau khi khóa; không dùng để sửa compiler/prompt.
CREATE TABLE oracle_fixture.loans (
    accession TEXT PRIMARY KEY, category TEXT NOT NULL,
    overdue_days INTEGER, fine NUMERIC(18, 2)
);
INSERT INTO oracle_fixture.loans VALUES
('0001', 'science', 2, 1.25),
('0002', 'history', NULL, NULL),
('0003', 'science', 0, 0.00);
