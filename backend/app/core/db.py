from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings
from app.core.security import hash_password


DEMO_ASSETS = [
    ("compressor-17", "Compressor 17", "compressor", "plant-a", "line-1"),
    ("motor-08", "Motor 08", "motor", "plant-a", "line-2"),
    ("pump-04", "Pump 04", "pump", "plant-b", "line-1"),
    ("drive-21", "Drive 21", "drive", "plant-c", "line-3"),
    ("conveyor-11", "Conveyor 11", "conveyor", "plant-c", "line-4"),
    ("cooling-skid-03", "Cooling Skid 03", "cooling-system", "plant-d", "line-1"),
    ("motor-14", "Motor 14", "motor", "plant-d", "line-2"),
    ("pump-12", "Pump 12", "pump", "plant-b", "line-2"),
    ("compressor-22", "Compressor 22", "compressor", "plant-d", "line-3"),
    ("drive-09", "Drive 09", "drive", "plant-a", "line-3"),
]

DEMO_PLANTS = [
    (
        "plant-a",
        "Auravance East Plant",
        "Primary production plant for compressors and rotating assets.",
        "Dallas, TX",
        "32.7767",
        "-96.7970",
        "1200 Innovation Loop, Dallas, TX 75201",
        "Auravance Manufacturing",
    ),
    (
        "plant-b",
        "Auravance Gulf Plant",
        "Secondary process facility focused on fluid handling equipment.",
        "Houston, TX",
        "29.7604",
        "-95.3698",
        "84 Harbor Industrial Way, Houston, TX 77002",
        "Auravance Manufacturing",
    ),
    (
        "plant-c",
        "Auravance Midwest Plant",
        "Assembly and packaging facility focused on drives, conveyors, and balance-of-plant utilities.",
        "Chicago, IL",
        "41.8781",
        "-87.6298",
        "2400 Foundry Court, Chicago, IL 60616",
        "Auravance Manufacturing",
    ),
    (
        "plant-d",
        "Auravance West Plant",
        "High-volume automation site supporting cooling skids, pumps, and digital utility systems.",
        "Phoenix, AZ",
        "33.4484",
        "-112.0740",
        "7800 Desert Automation Blvd, Phoenix, AZ 85004",
        "Auravance Manufacturing",
    ),
]

DEMO_VENDORS = [
    (
        "vendor-001",
        "Atlas Copco Services",
        "OEM",
        "Maria Chen",
        "maria.chen@atlascopco.example",
        "+1 214 555 0101",
        "400 Service Parkway, Dallas, TX",
        "24-hour response",
        "Active",
    ),
    (
        "vendor-002",
        "Siemens Motion Partners",
        "Service Partner",
        "David Ortiz",
        "dortiz@siemens-partners.example",
        "+1 469 555 0184",
        "850 Automation Ave, Plano, TX",
        "48-hour response",
        "Active",
    ),
    (
        "vendor-003",
        "FlowCore Industrial",
        "Parts Supplier",
        "Nia Brooks",
        "nia.brooks@flowcore.example",
        "+1 713 555 0127",
        "95 Port Logistics Rd, Houston, TX",
        "Same-day spares",
        "Preferred",
    ),
    (
        "vendor-004",
        "ABB Motion Systems",
        "OEM",
        "Priya Menon",
        "priya.menon@abb-motion.example",
        "+1 312 555 0144",
        "1450 Lake Tech Center, Chicago, IL",
        "24-hour field response",
        "Active",
    ),
    (
        "vendor-005",
        "Desert Calibration Labs",
        "Calibration Vendor",
        "Jon Mercer",
        "jon.mercer@dclabs.example",
        "+1 602 555 0189",
        "58 Precision Park, Phoenix, AZ",
        "72-hour calibration turnaround",
        "Onboarding",
    ),
    (
        "vendor-006",
        "Schneider Process Services",
        "Service Partner",
        "Elena Ruiz",
        "elena.ruiz@schneider-process.example",
        "+1 469 555 0118",
        "220 Gridline Drive, Irving, TX",
        "Remote triage in 4 hours",
        "Active",
    ),
    (
        "vendor-007",
        "BearingHub Industrial",
        "Parts Supplier",
        "Marcus Hale",
        "marcus.hale@bearinghub.example",
        "+1 713 555 0192",
        "330 Distribution Row, Pasadena, TX",
        "Critical spare dispatch in 6 hours",
        "Preferred",
    ),
]

DEMO_EQUIPMENT = [
    (
        "eq-1001",
        "compressor-17",
        "CMP-017",
        "Compressor 17",
        "Atlas Copco GA75",
        "Compressor",
        "Main compressed air unit for line 1.",
        "plant-a",
        "Line 1 Utility Bay",
        "Running",
        "Atlas Copco",
        "AC-GA75-2025-441",
        "AUR-CMP-017",
        "High",
        "2025-01-15",
        "2025-01-28",
        "Predictive",
        "2028-01-28",
        "vendor-001",
    ),
    (
        "eq-1002",
        "motor-08",
        "MTR-008",
        "Motor 08",
        "Siemens SIMOTICS GP150",
        "Motor",
        "High-torque motor driving the packaging conveyor.",
        "plant-a",
        "Packaging Cell",
        "Warning",
        "Siemens",
        "SM-GP150-008",
        "AUR-MTR-008",
        "Medium",
        "2024-09-10",
        "2024-09-14",
        "Condition Based",
        "2027-09-14",
        "vendor-002",
    ),
    (
        "eq-1003",
        "pump-04",
        "PMP-004",
        "Pump 04",
        "Grundfos CR 32",
        "Pump",
        "Recirculation pump supporting process cooling loop.",
        "plant-b",
        "Cooling Gallery",
        "Maintenance Due",
        "Grundfos",
        "GF-CR32-004",
        "AUR-PMP-004",
        "High",
        "2023-12-01",
        "2023-12-09",
        "Preventive",
        "2026-12-09",
        "vendor-003",
    ),
    (
        "eq-1004",
        "drive-21",
        "DRV-021",
        "Drive 21",
        "Schneider Altivar Process Drive",
        "Drive",
        "Variable frequency drive controlling the high-speed blending line.",
        "plant-c",
        "Blend Hall",
        "Running",
        "Schneider Electric",
        "SE-ATV-021",
        "AUR-DRV-021",
        "Medium",
        "2025-02-04",
        "2025-02-11",
        "Condition Based",
        "2028-02-11",
        "vendor-006",
    ),
    (
        "eq-1005",
        "conveyor-11",
        "CON-011",
        "Conveyor 11",
        "Siemens SIMOTICS GP150",
        "Conveyor",
        "Finished goods conveyor with motorized zone control and jam detection.",
        "plant-c",
        "Outbound Packaging",
        "Warning",
        "Siemens",
        "SM-CON-011",
        "AUR-CON-011",
        "Medium",
        "2024-08-18",
        "2024-08-23",
        "Predictive",
        "2027-08-23",
        "vendor-002",
    ),
    (
        "eq-1006",
        "cooling-skid-03",
        "CLG-003",
        "Cooling Skid 03",
        "Grundfos CR 32",
        "Cooling System",
        "Closed-loop process cooling skid serving packaging and electrical rooms.",
        "plant-d",
        "Utilities Yard",
        "Running",
        "Grundfos",
        "GF-CLG-003",
        "AUR-CLG-003",
        "High",
        "2024-04-09",
        "2024-04-15",
        "Preventive",
        "2027-04-15",
        "vendor-003",
    ),
    (
        "eq-1007",
        "motor-14",
        "MTR-014",
        "Motor 14",
        "ABB Baldor Reliance M3BP",
        "Motor",
        "Primary mixer drive motor on the resin dosing platform.",
        "plant-d",
        "Mixing Cell",
        "Standby",
        "ABB",
        "ABB-M3BP-014",
        "AUR-MTR-014",
        "High",
        "2023-10-06",
        "2023-10-12",
        "Condition Based",
        "2026-10-12",
        "vendor-004",
    ),
    (
        "eq-1008",
        "pump-12",
        "PMP-012",
        "Pump 12",
        "Grundfos CR 32",
        "Pump",
        "Transfer pump feeding recirculation tanks during high-load shifts.",
        "plant-b",
        "Process Corridor B",
        "Running",
        "Grundfos",
        "GF-CR32-012",
        "AUR-PMP-012",
        "Medium",
        "2025-03-01",
        "2025-03-05",
        "Predictive",
        "2028-03-05",
        "vendor-003",
    ),
    (
        "eq-1009",
        "compressor-22",
        "CMP-022",
        "Compressor 22",
        "Atlas Copco GA75",
        "Compressor",
        "Backup compressed air unit supporting the west utility loop.",
        "plant-d",
        "Utility Bay 2",
        "Maintenance Due",
        "Atlas Copco",
        "AC-GA75-2024-922",
        "AUR-CMP-022",
        "High",
        "2024-06-12",
        "2024-06-18",
        "Preventive",
        "2027-06-18",
        "vendor-001",
    ),
    (
        "eq-1010",
        "drive-09",
        "DRV-009",
        "Drive 09",
        "Schneider Altivar Process Drive",
        "Drive",
        "Low-voltage process drive for filler line synchronization.",
        "plant-a",
        "Filler Hall",
        "Running",
        "Schneider Electric",
        "SE-ATV-009",
        "AUR-DRV-009",
        "Medium",
        "2024-11-21",
        "2024-11-28",
        "Predictive",
        "2027-11-28",
        "vendor-006",
    ),
]

DEMO_SENSORS = [
    ("sensor-001", "eq-1001", "TT-CMP17-01", "Discharge Temperature", "temperature", "C", "Compressor skid", 1),
    ("sensor-002", "eq-1001", "VT-CMP17-02", "Bearing Vibration", "vibration", "RMS", "Drive end bearing", 1),
    ("sensor-003", "eq-1001", "PT-CMP17-03", "Line Pressure", "pressure", "bar", "Discharge manifold", 1),
    ("sensor-004", "eq-1002", "CT-MTR08-01", "Motor Current", "current", "A", "Motor control center", 1),
    ("sensor-005", "eq-1003", "PT-PMP04-01", "Pump Pressure", "pressure", "bar", "Pump outlet", 1),
    ("sensor-006", "eq-1005", "TT-CON11-01", "Motor Housing Temperature", "temperature", "C", "Conveyor motor", 0),
    ("sensor-007", "eq-1006", "FT-CLG03-01", "Cooling Loop Flow", "flow", "LPM", "Cooling skid outlet", 1),
    ("sensor-008", "eq-1009", "DP-CMP22-01", "Separator Differential Pressure", "pressure_delta", "bar", "Separator housing", 1),
]

DEMO_USERS = [
    ("user-000", "Yashas Chandra", "yashas@auravance.demo", "Admin", "All Plants", "Active", "2026-05-16 08:45"),
    ("user-001", "Ananya Rao", "ananya.rao@auravance.example", "Admin", "All Plants", "Active", "2026-05-16 08:20"),
    ("user-002", "Rahul Singh", "rahul.singh@auravance.example", "Technician", "Auravance East Plant", "Active", "2026-05-16 07:54"),
    ("user-003", "Leena Patel", "leena.patel@auravance.example", "Maintenance Planner", "Auravance Gulf Plant", "Pending Invite", "Never"),
    ("user-004", "Marcus Hale", "marcus.hale@auravance.example", "Reliability Engineer", "Auravance East Plant", "Active", "2026-05-16 09:12"),
    ("user-005", "Elena Ruiz", "elena.ruiz@auravance.example", "Plant Manager", "Auravance Midwest Plant", "Active", "2026-05-16 08:58"),
    ("user-006", "Jamal Carter", "jamal.carter@auravance.example", "Viewer", "Auravance West Plant", "Active", "2026-05-15 17:41"),
    ("user-007", "Mia Alvarez", "mia.alvarez@auravance.example", "Technician", "Auravance Gulf Plant", "Active", "2026-05-16 06:52"),
    ("user-008", "Chris Osei", "chris.osei@auravance.example", "Maintenance Planner", "Auravance West Plant", "Suspended", "2026-05-08 11:24"),
]

DEMO_USER_PASSWORDS = {
    "yashas@auravance.demo": "Auravance@123",
    "rahul.singh@auravance.example": "Technician@123",
}

DEMO_MAINTENANCE_SCHEDULES = [
    ("ms-1001", "Compressor 17", "Predictive", "Every 30 days", "2026-05-21", "Reliability Team", "On Track"),
    ("ms-1002", "Pump 04", "Preventive", "Every 14 days", "2026-05-18", "Maintenance Planner", "Upcoming"),
    ("ms-1003", "Motor 08", "Condition Based", "Triggered by vibration", "2026-05-16", "Line 2 Supervisor", "Action Needed"),
    ("ms-1004", "Drive 21", "Condition Based", "Weekly health review", "2026-05-20", "Controls Engineer", "On Track"),
    ("ms-1005", "Cooling Skid 03", "Preventive", "Every 21 days", "2026-05-22", "Utilities Supervisor", "On Track"),
    ("ms-1006", "Compressor 22", "Preventive", "Every 10 days", "2026-05-17", "Maintenance Planner", "Upcoming"),
    ("ms-1007", "Conveyor 11", "Predictive", "Triggered by thermal drift", "2026-05-18", "Packaging Reliability Lead", "Action Needed"),
    ("ms-1008", "Pump 12", "Condition Based", "Triggered by seal leakage score", "2026-05-23", "Process Engineer", "On Track"),
]

DEMO_WORK_ORDERS = [
    ("wo-2041", "Inspect Compressor 17 bearing assembly", "Compressor 17", "High", "Inspection", "Auravance AI Engine", "R. Singh", "2026-05-17", "Open", "Elevated vibration and heat trend exceeded warning threshold."),
    ("wo-2042", "Review Motor 08 load profile", "Motor 08", "Medium", "Diagnostic", "Plant Manager", "L. Patel", "2026-05-19", "In Progress", "Current draw is rising during peak packaging shifts."),
    ("wo-2043", "Replace Pump 04 mechanical seal kit", "Pump 04", "Critical", "Repair", "Reliability Engineer", "M. Alvarez", "2026-05-17", "Waiting Parts", "Seal leakage risk is increasing and spare kit is in transit from FlowCore Industrial."),
    ("wo-2044", "Calibrate Cooling Skid 03 pressure transmitters", "Cooling Skid 03", "Medium", "Calibration", "Utilities Supervisor", "J. Mercer", "2026-05-22", "Open", "Quarterly calibration due for dual pressure transmitters and flow interlock verification."),
    ("wo-2045", "Inspect Conveyor 11 motor fan shroud", "Conveyor 11", "Low", "Inspection", "Packaging Lead", "T. Monroe", "2026-05-20", "Open", "Thermal trend suggests reduced airflow near the motor housing during second shift."),
    ("wo-2046", "Analyze Drive 21 harmonic distortion event", "Drive 21", "High", "Diagnostic", "Controls Engineer", "E. Ruiz", "2026-05-18", "In Progress", "Momentary bus instability was observed during a synchronized startup sequence on blend hall equipment."),
    ("wo-2047", "Shutdown service for Compressor 22 oil separator", "Compressor 22", "High", "Shutdown", "Maintenance Planner", "R. Singh", "2026-05-24", "Open", "Separator differential pressure is trending upward and requires planned downtime replacement."),
]

DEMO_DEFECTS = [
    ("df-301", "Pump 04", "SEAL-LEAK", "High", "Observed", "2026-05-14", "Pressure oscillation suggests possible valve leak or seal degradation.", "Inspection Team"),
    ("df-302", "Compressor 17", "BRG-WEAR", "Critical", "Mitigation Planned", "2026-05-15", "Bearing wear pattern detected from temperature and vibration alignment.", "Reliability Engineer"),
    ("df-303", "Motor 08", "LOAD-IMBAL", "Medium", "Under Review", "2026-05-13", "Phase current variance indicates intermittent load imbalance during conveyor surge conditions.", "Electrical Team"),
    ("df-304", "Conveyor 11", "FAN-OBSTR", "Medium", "Observed", "2026-05-12", "Cooling fan shroud shows contamination buildup, reducing motor airflow during peak production.", "Packaging Maintenance"),
    ("df-305", "Drive 21", "THD-SPIKE", "High", "Mitigation Planned", "2026-05-16", "Short-duration harmonic distortion spike observed during synchronized startup with upstream mixer loads.", "Controls Engineer"),
    ("df-306", "Cooling Skid 03", "TX-DRIFT", "Low", "Observed", "2026-05-11", "Pressure transmitter pair is showing small calibration drift beyond internal tolerance band.", "Instrumentation Team"),
    ("df-307", "Compressor 22", "SEP-DP-HI", "High", "Under Review", "2026-05-15", "Oil separator differential pressure is elevated relative to historical baseline at comparable demand.", "Utilities Supervisor"),
    ("df-308", "Pump 12", "CAV-ONSET", "Medium", "Resolved", "2026-05-09", "Early cavitation signature was detected and corrected after suction strainer cleaning and line flush.", "Process Engineer"),
]


def _database_path() -> Path:
    path = Path(settings.demo_db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(_database_path(), detect_types=sqlite3.PARSE_DECLTYPES)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _ensure_column(cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    existing = {row["name"] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                plant_id TEXT NOT NULL,
                line_id TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                temperature_c REAL,
                vibration_rms REAL,
                pressure_bar REAL,
                current_a REAL,
                FOREIGN KEY(asset_id) REFERENCES assets(asset_id)
            );

            CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(asset_id) REFERENCES assets(asset_id)
            );

            CREATE TABLE IF NOT EXISTS plants (
                plant_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                location TEXT NOT NULL,
                latitude TEXT NOT NULL,
                longitude TEXT NOT NULL,
                address TEXT NOT NULL,
                organization TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS vendors (
                vendor_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                vendor_type TEXT NOT NULL,
                contact_person TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                address TEXT NOT NULL,
                sla_level TEXT NOT NULL,
                status TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS equipment (
                equipment_id TEXT PRIMARY KEY,
                asset_id TEXT UNIQUE,
                equipment_number TEXT NOT NULL,
                name TEXT NOT NULL,
                model TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                plant_id TEXT NOT NULL,
                area TEXT NOT NULL,
                status TEXT NOT NULL,
                manufacturer TEXT NOT NULL,
                serial_number TEXT NOT NULL,
                asset_tag TEXT NOT NULL,
                criticality TEXT NOT NULL,
                install_date TEXT NOT NULL,
                commissioning_date TEXT NOT NULL,
                maintenance_strategy TEXT NOT NULL,
                warranty_expiry TEXT NOT NULL,
                vendor_id TEXT NOT NULL,
                FOREIGN KEY(asset_id) REFERENCES assets(asset_id),
                FOREIGN KEY(plant_id) REFERENCES plants(plant_id),
                FOREIGN KEY(vendor_id) REFERENCES vendors(vendor_id)
            );

            CREATE TABLE IF NOT EXISTS sensors (
                sensor_id TEXT PRIMARY KEY,
                equipment_id TEXT NOT NULL,
                tag TEXT NOT NULL,
                name TEXT NOT NULL,
                sensor_type TEXT NOT NULL,
                unit TEXT NOT NULL,
                location TEXT NOT NULL,
                is_critical INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(equipment_id) REFERENCES equipment(equipment_id)
            );

            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL,
                plant_scope TEXT NOT NULL,
                status TEXT NOT NULL,
                last_login TEXT NOT NULL,
                password_hash TEXT
            );

            CREATE TABLE IF NOT EXISTS maintenance_schedules (
                schedule_id TEXT PRIMARY KEY,
                asset_name TEXT NOT NULL,
                schedule_type TEXT NOT NULL,
                cadence TEXT NOT NULL,
                next_due TEXT NOT NULL,
                owner TEXT NOT NULL,
                status TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS work_orders (
                work_order_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                asset_name TEXT NOT NULL,
                priority TEXT NOT NULL,
                work_type TEXT NOT NULL,
                requested_by TEXT NOT NULL,
                assignee TEXT NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL,
                summary TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS defects (
                defect_id TEXT PRIMARY KEY,
                asset_name TEXT NOT NULL,
                defect_code TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                discovered_on TEXT NOT NULL,
                description TEXT NOT NULL,
                owner TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS dataset_catalog (
                dataset_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                source TEXT NOT NULL,
                raw_path TEXT NOT NULL,
                extracted_path TEXT,
                processed_path TEXT,
                status TEXT NOT NULL,
                record_count INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                last_synced_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS dataset_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                row_count INTEGER,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(dataset_id) REFERENCES dataset_catalog(dataset_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS knowledge_documents (
                document_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                vendor TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_path TEXT NOT NULL UNIQUE,
                processed_path TEXT NOT NULL,
                chunk_path TEXT NOT NULL,
                page_count INTEGER NOT NULL DEFAULT 0,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                token_count INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                vector_json TEXT NOT NULL DEFAULT '{}',
                embedding_json TEXT NOT NULL DEFAULT '[]',
                FOREIGN KEY(document_id) REFERENCES knowledge_documents(document_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS knowledge_corpus_stats (
                token TEXT PRIMARY KEY,
                document_frequency INTEGER NOT NULL,
                idf REAL NOT NULL,
                chunk_count INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        _ensure_column(cursor, "knowledge_chunks", "vector_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(cursor, "knowledge_chunks", "embedding_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(cursor, "users", "password_hash", "TEXT")
        connection.commit()
    seed_demo_assets()
    seed_master_data()


def seed_demo_assets() -> None:
    with closing(get_connection()) as connection:
        connection.executemany(
            """
            INSERT OR IGNORE INTO assets (asset_id, name, asset_type, plant_id, line_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            DEMO_ASSETS,
        )
        connection.commit()


def seed_master_data() -> None:
    with closing(get_connection()) as connection:
        connection.executemany(
            """
            INSERT OR IGNORE INTO plants (
                plant_id, name, description, location, latitude, longitude, address, organization
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            DEMO_PLANTS,
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO vendors (
                vendor_id, name, vendor_type, contact_person, email, phone, address, sla_level, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            DEMO_VENDORS,
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO equipment (
                equipment_id, asset_id, equipment_number, name, model, category, description, plant_id,
                area, status, manufacturer, serial_number, asset_tag, criticality, install_date,
                commissioning_date, maintenance_strategy, warranty_expiry, vendor_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            DEMO_EQUIPMENT,
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO sensors (
                sensor_id, equipment_id, tag, name, sensor_type, unit, location, is_critical
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            DEMO_SENSORS,
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO users (
                user_id, full_name, email, role, plant_scope, status, last_login
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            DEMO_USERS,
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO maintenance_schedules (
                schedule_id, asset_name, schedule_type, cadence, next_due, owner, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            DEMO_MAINTENANCE_SCHEDULES,
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO work_orders (
                work_order_id, title, asset_name, priority, work_type, requested_by, assignee,
                due_date, status, summary
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            DEMO_WORK_ORDERS,
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO defects (
                defect_id, asset_name, defect_code, severity, status, discovered_on, description, owner
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            DEMO_DEFECTS,
        )
        for user_id, _, email, _, _, _, _ in DEMO_USERS:
            default_password = DEMO_USER_PASSWORDS.get(email, "Welcome@123")
            connection.execute(
                """
                UPDATE users
                SET password_hash = COALESCE(password_hash, ?)
                WHERE user_id = ?
                """,
                (hash_password(default_password), user_id),
            )
        connection.commit()


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def upsert_dataset(dataset: dict, artifacts: list[dict] | None = None) -> None:
    with closing(get_connection()) as connection:
        connection.execute(
            """
            INSERT INTO dataset_catalog (
                dataset_id,
                name,
                source,
                raw_path,
                extracted_path,
                processed_path,
                status,
                record_count,
                notes,
                last_synced_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(dataset_id) DO UPDATE SET
                name = excluded.name,
                source = excluded.source,
                raw_path = excluded.raw_path,
                extracted_path = excluded.extracted_path,
                processed_path = excluded.processed_path,
                status = excluded.status,
                record_count = excluded.record_count,
                notes = excluded.notes,
                last_synced_at = excluded.last_synced_at
            """,
            (
                dataset["dataset_id"],
                dataset["name"],
                dataset["source"],
                dataset["raw_path"],
                dataset.get("extracted_path"),
                dataset.get("processed_path"),
                dataset["status"],
                dataset.get("record_count", 0),
                dataset.get("notes"),
                dataset.get("last_synced_at", _utc_now_iso()),
            ),
        )

        if artifacts is not None:
            connection.execute("DELETE FROM dataset_artifacts WHERE dataset_id = ?", (dataset["dataset_id"],))
            connection.executemany(
                """
                INSERT INTO dataset_artifacts (
                    dataset_id,
                    artifact_type,
                    file_path,
                    row_count,
                    metadata_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        dataset["dataset_id"],
                        artifact["artifact_type"],
                        artifact["file_path"],
                        artifact.get("row_count"),
                        json.dumps(artifact.get("metadata", {})),
                        artifact.get("created_at", _utc_now_iso()),
                    )
                    for artifact in artifacts
                ],
            )

        connection.commit()


def fetch_datasets() -> list[dict]:
    with closing(get_connection()) as connection:
        datasets = connection.execute(
            """
            SELECT
                dataset_id,
                name,
                source,
                raw_path,
                extracted_path,
                processed_path,
                status,
                record_count,
                notes,
                last_synced_at
            FROM dataset_catalog
            ORDER BY name
            """
        ).fetchall()

        results: list[dict] = []
        for dataset in datasets:
            artifacts = connection.execute(
                """
                SELECT artifact_type, file_path, row_count, metadata_json, created_at
                FROM dataset_artifacts
                WHERE dataset_id = ?
                ORDER BY artifact_type, file_path
                """,
                (dataset["dataset_id"],),
            ).fetchall()

            results.append(
                {
                    **dict(dataset),
                    "artifacts": [
                        {
                            "artifact_type": artifact["artifact_type"],
                            "file_path": artifact["file_path"],
                            "row_count": artifact["row_count"],
                            "metadata": json.loads(artifact["metadata_json"] or "{}"),
                            "created_at": artifact["created_at"],
                        }
                        for artifact in artifacts
                    ],
                }
            )

        return results


def upsert_knowledge_document(document: dict, chunks: list[dict]) -> None:
    with closing(get_connection()) as connection:
        connection.execute(
            """
            INSERT INTO knowledge_documents (
                document_id,
                title,
                vendor,
                source_type,
                source_path,
                processed_path,
                chunk_path,
                page_count,
                chunk_count,
                status,
                notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                title = excluded.title,
                vendor = excluded.vendor,
                source_type = excluded.source_type,
                source_path = excluded.source_path,
                processed_path = excluded.processed_path,
                chunk_path = excluded.chunk_path,
                page_count = excluded.page_count,
                chunk_count = excluded.chunk_count,
                status = excluded.status,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                document["document_id"],
                document["title"],
                document["vendor"],
                document["source_type"],
                document["source_path"],
                document["processed_path"],
                document["chunk_path"],
                document.get("page_count", 0),
                document.get("chunk_count", 0),
                document["status"],
                document.get("notes"),
                document.get("created_at", _utc_now_iso()),
                document.get("updated_at", _utc_now_iso()),
            ),
        )
        connection.execute("DELETE FROM knowledge_chunks WHERE document_id = ?", (document["document_id"],))
        connection.executemany(
            """
            INSERT INTO knowledge_chunks (
                document_id,
                chunk_index,
                content,
                token_count,
                metadata_json,
                vector_json,
                embedding_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    document["document_id"],
                    chunk["chunk_index"],
                    chunk["content"],
                    chunk.get("token_count", 0),
                    json.dumps(chunk.get("metadata", {})),
                    json.dumps(chunk.get("vector", {})),
                    json.dumps(chunk.get("embedding", [])),
                )
                for chunk in chunks
            ],
        )
        connection.commit()


def replace_knowledge_corpus_stats(stats: list[dict]) -> None:
    with closing(get_connection()) as connection:
        connection.execute("DELETE FROM knowledge_corpus_stats")
        connection.executemany(
            """
            INSERT INTO knowledge_corpus_stats (
                token,
                document_frequency,
                idf,
                chunk_count,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    item["token"],
                    item["document_frequency"],
                    item["idf"],
                    item["chunk_count"],
                    item.get("updated_at", _utc_now_iso()),
                )
                for item in stats
            ],
        )
        connection.commit()


def fetch_knowledge_documents() -> list[dict]:
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT
                document_id,
                title,
                vendor,
                source_type,
                source_path,
                processed_path,
                chunk_path,
                page_count,
                chunk_count,
                status,
                notes,
                created_at,
                updated_at
            FROM knowledge_documents
            ORDER BY vendor, title
            """
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_knowledge_chunks() -> list[dict]:
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT
                kc.document_id,
                kc.chunk_index,
                kc.content,
                kc.token_count,
                kc.metadata_json,
                kc.vector_json,
                kc.embedding_json,
                kd.title,
                kd.vendor,
                kd.source_path,
                kd.source_type
            FROM knowledge_chunks kc
            JOIN knowledge_documents kd ON kd.document_id = kc.document_id
            ORDER BY kd.vendor, kd.title, kc.chunk_index
            """
        ).fetchall()
    return [
        {
            **dict(row),
            "metadata": json.loads(row["metadata_json"] or "{}"),
            "vector": json.loads(row["vector_json"] or "{}"),
            "embedding": json.loads(row["embedding_json"] or "[]"),
        }
        for row in rows
    ]


def fetch_knowledge_corpus_stats() -> dict[str, dict]:
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT token, document_frequency, idf, chunk_count, updated_at
            FROM knowledge_corpus_stats
            """
        ).fetchall()
    return {
        row["token"]: {
            "document_frequency": row["document_frequency"],
            "idf": row["idf"],
            "chunk_count": row["chunk_count"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    }


def fetch_knowledge_index_stats() -> dict[str, int]:
    with closing(get_connection()) as connection:
        documents = connection.execute("SELECT COUNT(*) AS count FROM knowledge_documents").fetchone()["count"]
        chunks = connection.execute("SELECT COUNT(*) AS count FROM knowledge_chunks").fetchone()["count"]
        embedded_chunks = connection.execute(
            "SELECT COUNT(*) AS count FROM knowledge_chunks WHERE embedding_json IS NOT NULL AND embedding_json != '[]'"
        ).fetchone()["count"]
    return {
        "documents": int(documents),
        "chunks": int(chunks),
        "embedded_chunks": int(embedded_chunks),
    }
