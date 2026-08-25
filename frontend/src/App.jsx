import { useEffect, useMemo, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const SESSION_STORAGE_KEY = "auravance.currentUser";

const NAV_ITEMS = [
  { id: "monitoring", label: "Monitoring", group: "Operations" },
  { id: "rootcause", label: "Root Cause Analysis", group: "Operations" },
  { id: "plants", label: "Plant Info", group: "Master Data" },
  { id: "equipment", label: "Equipment Master", group: "Master Data" },
  { id: "vendors", label: "Vendor Management", group: "Master Data" },
  { id: "schedules", label: "Maintenance Schedules", group: "Execution" },
  { id: "workorders", label: "Work Order Mgmt", group: "Execution" },
  { id: "defects", label: "Defects View", group: "Execution" },
  { id: "users", label: "User Mgmt", group: "Admin" },
];

const EQUIPMENT_MODELS = [
  "Atlas Copco GA75",
  "Siemens SIMOTICS GP150",
  "Grundfos CR 32",
  "ABB Baldor Reliance M3BP",
  "Schneider Altivar Process Drive",
];

const EQUIPMENT_CATEGORIES = [
  "Compressor",
  "Motor",
  "Pump",
  "Conveyor",
  "Drive",
  "Cooling System",
];

const VENDOR_TYPES = ["OEM", "Service Partner", "Parts Supplier", "Calibration Vendor"];
const USER_ROLES = ["Admin", "Plant Manager", "Maintenance Planner", "Reliability Engineer", "Technician", "Viewer"];

const INITIAL_PLANTS = [
  {
    id: "plant-a",
    name: "Auravance East Plant",
    description: "Primary production plant for compressors and rotating assets.",
    location: "Dallas, TX",
    latitude: "32.7767",
    longitude: "-96.7970",
    address: "1200 Innovation Loop, Dallas, TX 75201",
    organization: "Auravance Manufacturing",
  },
  {
    id: "plant-b",
    name: "Auravance Gulf Plant",
    description: "Secondary process facility focused on fluid handling equipment.",
    location: "Houston, TX",
    latitude: "29.7604",
    longitude: "-95.3698",
    address: "84 Harbor Industrial Way, Houston, TX 77002",
    organization: "Auravance Manufacturing",
  },
  {
    id: "plant-c",
    name: "Auravance Midwest Plant",
    description: "Assembly and packaging facility focused on drives, conveyors, and balance-of-plant utilities.",
    location: "Chicago, IL",
    latitude: "41.8781",
    longitude: "-87.6298",
    address: "2400 Foundry Court, Chicago, IL 60616",
    organization: "Auravance Manufacturing",
  },
  {
    id: "plant-d",
    name: "Auravance West Plant",
    description: "High-volume automation site supporting cooling skids, pumps, and digital utility systems.",
    location: "Phoenix, AZ",
    latitude: "33.4484",
    longitude: "-112.0740",
    address: "7800 Desert Automation Blvd, Phoenix, AZ 85004",
    organization: "Auravance Manufacturing",
  },
];

const INITIAL_VENDORS = [
  {
    id: "vendor-001",
    name: "Atlas Copco Services",
    type: "OEM",
    contactPerson: "Maria Chen",
    email: "maria.chen@atlascopco.example",
    phone: "+1 214 555 0101",
    address: "400 Service Parkway, Dallas, TX",
    slaLevel: "24-hour response",
    status: "Active",
  },
  {
    id: "vendor-002",
    name: "Siemens Motion Partners",
    type: "Service Partner",
    contactPerson: "David Ortiz",
    email: "dortiz@siemens-partners.example",
    phone: "+1 469 555 0184",
    address: "850 Automation Ave, Plano, TX",
    slaLevel: "48-hour response",
    status: "Active",
  },
  {
    id: "vendor-003",
    name: "FlowCore Industrial",
    type: "Parts Supplier",
    contactPerson: "Nia Brooks",
    email: "nia.brooks@flowcore.example",
    phone: "+1 713 555 0127",
    address: "95 Port Logistics Rd, Houston, TX",
    slaLevel: "Same-day spares",
    status: "Preferred",
  },
  {
    id: "vendor-004",
    name: "ABB Motion Systems",
    type: "OEM",
    contactPerson: "Priya Menon",
    email: "priya.menon@abb-motion.example",
    phone: "+1 312 555 0144",
    address: "1450 Lake Tech Center, Chicago, IL",
    slaLevel: "24-hour field response",
    status: "Active",
  },
  {
    id: "vendor-005",
    name: "Desert Calibration Labs",
    type: "Calibration Vendor",
    contactPerson: "Jon Mercer",
    email: "jon.mercer@dclabs.example",
    phone: "+1 602 555 0189",
    address: "58 Precision Park, Phoenix, AZ",
    slaLevel: "72-hour calibration turnaround",
    status: "Onboarding",
  },
  {
    id: "vendor-006",
    name: "Schneider Process Services",
    type: "Service Partner",
    contactPerson: "Elena Ruiz",
    email: "elena.ruiz@schneider-process.example",
    phone: "+1 469 555 0118",
    address: "220 Gridline Drive, Irving, TX",
    slaLevel: "Remote triage in 4 hours",
    status: "Active",
  },
  {
    id: "vendor-007",
    name: "BearingHub Industrial",
    type: "Parts Supplier",
    contactPerson: "Marcus Hale",
    email: "marcus.hale@bearinghub.example",
    phone: "+1 713 555 0192",
    address: "330 Distribution Row, Pasadena, TX",
    slaLevel: "Critical spare dispatch in 6 hours",
    status: "Preferred",
  },
];

const INITIAL_EQUIPMENT = [
  {
    id: "eq-1001",
    equipmentNumber: "CMP-017",
    name: "Compressor 17",
    model: "Atlas Copco GA75",
    category: "Compressor",
    description: "Main compressed air unit for line 1.",
    plantId: "plant-a",
    area: "Line 1 Utility Bay",
    status: "Running",
    manufacturer: "Atlas Copco",
    serialNumber: "AC-GA75-2025-441",
    assetTag: "AUR-CMP-017",
    criticality: "High",
    installDate: "2025-01-15",
    commissioningDate: "2025-01-28",
    maintenanceStrategy: "Predictive",
    warrantyExpiry: "2028-01-28",
    vendorId: "vendor-001",
  },
  {
    id: "eq-1002",
    equipmentNumber: "MTR-008",
    name: "Motor 08",
    model: "Siemens SIMOTICS GP150",
    category: "Motor",
    description: "High-torque motor driving the packaging conveyor.",
    plantId: "plant-a",
    area: "Packaging Cell",
    status: "Warning",
    manufacturer: "Siemens",
    serialNumber: "SM-GP150-008",
    assetTag: "AUR-MTR-008",
    criticality: "Medium",
    installDate: "2024-09-10",
    commissioningDate: "2024-09-14",
    maintenanceStrategy: "Condition Based",
    warrantyExpiry: "2027-09-14",
    vendorId: "vendor-002",
  },
  {
    id: "eq-1003",
    equipmentNumber: "PMP-004",
    name: "Pump 04",
    model: "Grundfos CR 32",
    category: "Pump",
    description: "Recirculation pump supporting process cooling loop.",
    plantId: "plant-b",
    area: "Cooling Gallery",
    status: "Maintenance Due",
    manufacturer: "Grundfos",
    serialNumber: "GF-CR32-004",
    assetTag: "AUR-PMP-004",
    criticality: "High",
    installDate: "2023-12-01",
    commissioningDate: "2023-12-09",
    maintenanceStrategy: "Preventive",
    warrantyExpiry: "2026-12-09",
    vendorId: "vendor-003",
  },
  {
    id: "eq-1004",
    equipmentNumber: "DRV-021",
    name: "Drive 21",
    model: "Schneider Altivar Process Drive",
    category: "Drive",
    description: "Variable frequency drive controlling the high-speed blending line.",
    plantId: "plant-c",
    area: "Blend Hall",
    status: "Running",
    manufacturer: "Schneider Electric",
    serialNumber: "SE-ATV-021",
    assetTag: "AUR-DRV-021",
    criticality: "Medium",
    installDate: "2025-02-04",
    commissioningDate: "2025-02-11",
    maintenanceStrategy: "Condition Based",
    warrantyExpiry: "2028-02-11",
    vendorId: "vendor-006",
  },
  {
    id: "eq-1005",
    equipmentNumber: "CON-011",
    name: "Conveyor 11",
    model: "Siemens SIMOTICS GP150",
    category: "Conveyor",
    description: "Finished goods conveyor with motorized zone control and jam detection.",
    plantId: "plant-c",
    area: "Outbound Packaging",
    status: "Warning",
    manufacturer: "Siemens",
    serialNumber: "SM-CON-011",
    assetTag: "AUR-CON-011",
    criticality: "Medium",
    installDate: "2024-08-18",
    commissioningDate: "2024-08-23",
    maintenanceStrategy: "Predictive",
    warrantyExpiry: "2027-08-23",
    vendorId: "vendor-002",
  },
  {
    id: "eq-1006",
    equipmentNumber: "CLG-003",
    name: "Cooling Skid 03",
    model: "Grundfos CR 32",
    category: "Cooling System",
    description: "Closed-loop process cooling skid serving packaging and electrical rooms.",
    plantId: "plant-d",
    area: "Utilities Yard",
    status: "Running",
    manufacturer: "Grundfos",
    serialNumber: "GF-CLG-003",
    assetTag: "AUR-CLG-003",
    criticality: "High",
    installDate: "2024-04-09",
    commissioningDate: "2024-04-15",
    maintenanceStrategy: "Preventive",
    warrantyExpiry: "2027-04-15",
    vendorId: "vendor-003",
  },
  {
    id: "eq-1007",
    equipmentNumber: "MTR-014",
    name: "Motor 14",
    model: "ABB Baldor Reliance M3BP",
    category: "Motor",
    description: "Primary mixer drive motor on the resin dosing platform.",
    plantId: "plant-d",
    area: "Mixing Cell",
    status: "Standby",
    manufacturer: "ABB",
    serialNumber: "ABB-M3BP-014",
    assetTag: "AUR-MTR-014",
    criticality: "High",
    installDate: "2023-10-06",
    commissioningDate: "2023-10-12",
    maintenanceStrategy: "Condition Based",
    warrantyExpiry: "2026-10-12",
    vendorId: "vendor-004",
  },
  {
    id: "eq-1008",
    equipmentNumber: "PMP-012",
    name: "Pump 12",
    model: "Grundfos CR 32",
    category: "Pump",
    description: "Transfer pump feeding recirculation tanks during high-load shifts.",
    plantId: "plant-b",
    area: "Process Corridor B",
    status: "Running",
    manufacturer: "Grundfos",
    serialNumber: "GF-CR32-012",
    assetTag: "AUR-PMP-012",
    criticality: "Medium",
    installDate: "2025-03-01",
    commissioningDate: "2025-03-05",
    maintenanceStrategy: "Predictive",
    warrantyExpiry: "2028-03-05",
    vendorId: "vendor-003",
  },
  {
    id: "eq-1009",
    equipmentNumber: "CMP-022",
    name: "Compressor 22",
    model: "Atlas Copco GA75",
    category: "Compressor",
    description: "Backup compressed air unit supporting the west utility loop.",
    plantId: "plant-d",
    area: "Utility Bay 2",
    status: "Maintenance Due",
    manufacturer: "Atlas Copco",
    serialNumber: "AC-GA75-2024-922",
    assetTag: "AUR-CMP-022",
    criticality: "High",
    installDate: "2024-06-12",
    commissioningDate: "2024-06-18",
    maintenanceStrategy: "Preventive",
    warrantyExpiry: "2027-06-18",
    vendorId: "vendor-001",
  },
  {
    id: "eq-1010",
    equipmentNumber: "DRV-009",
    name: "Drive 09",
    model: "Schneider Altivar Process Drive",
    category: "Drive",
    description: "Low-voltage process drive for filler line synchronization.",
    plantId: "plant-a",
    area: "Filler Hall",
    status: "Running",
    manufacturer: "Schneider Electric",
    serialNumber: "SE-ATV-009",
    assetTag: "AUR-DRV-009",
    criticality: "Medium",
    installDate: "2024-11-21",
    commissioningDate: "2024-11-28",
    maintenanceStrategy: "Predictive",
    warrantyExpiry: "2027-11-28",
    vendorId: "vendor-006",
  },
];

const INITIAL_SCHEDULES = [
  {
    id: "ms-1001",
    assetName: "Compressor 17",
    scheduleType: "Predictive",
    cadence: "Every 30 days",
    nextDue: "2026-05-21",
    owner: "Reliability Team",
    status: "On Track",
  },
  {
    id: "ms-1002",
    assetName: "Pump 04",
    scheduleType: "Preventive",
    cadence: "Every 14 days",
    nextDue: "2026-05-18",
    owner: "Maintenance Planner",
    status: "Upcoming",
  },
  {
    id: "ms-1003",
    assetName: "Motor 08",
    scheduleType: "Condition Based",
    cadence: "Triggered by vibration",
    nextDue: "2026-05-16",
    owner: "Line 2 Supervisor",
    status: "Action Needed",
  },
  {
    id: "ms-1004",
    assetName: "Drive 21",
    scheduleType: "Condition Based",
    cadence: "Weekly health review",
    nextDue: "2026-05-20",
    owner: "Controls Engineer",
    status: "On Track",
  },
  {
    id: "ms-1005",
    assetName: "Cooling Skid 03",
    scheduleType: "Preventive",
    cadence: "Every 21 days",
    nextDue: "2026-05-22",
    owner: "Utilities Supervisor",
    status: "On Track",
  },
  {
    id: "ms-1006",
    assetName: "Compressor 22",
    scheduleType: "Preventive",
    cadence: "Every 10 days",
    nextDue: "2026-05-17",
    owner: "Maintenance Planner",
    status: "Upcoming",
  },
  {
    id: "ms-1007",
    assetName: "Conveyor 11",
    scheduleType: "Predictive",
    cadence: "Triggered by thermal drift",
    nextDue: "2026-05-18",
    owner: "Packaging Reliability Lead",
    status: "Action Needed",
  },
  {
    id: "ms-1008",
    assetName: "Pump 12",
    scheduleType: "Condition Based",
    cadence: "Triggered by seal leakage score",
    nextDue: "2026-05-23",
    owner: "Process Engineer",
    status: "On Track",
  },
];

const INITIAL_WORK_ORDERS = [
  {
    id: "wo-2041",
    title: "Inspect Compressor 17 bearing assembly",
    assetName: "Compressor 17",
    priority: "High",
    type: "Inspection",
    requestedBy: "Auravance AI Engine",
    assignee: "R. Singh",
    dueDate: "2026-05-17",
    status: "Open",
    summary: "Elevated vibration and heat trend exceeded warning threshold.",
  },
  {
    id: "wo-2042",
    title: "Review Motor 08 load profile",
    assetName: "Motor 08",
    priority: "Medium",
    type: "Diagnostic",
    requestedBy: "Plant Manager",
    assignee: "L. Patel",
    dueDate: "2026-05-19",
    status: "In Progress",
    summary: "Current draw is rising during peak packaging shifts.",
  },
  {
    id: "wo-2043",
    title: "Replace Pump 04 mechanical seal kit",
    assetName: "Pump 04",
    priority: "Critical",
    type: "Repair",
    requestedBy: "Reliability Engineer",
    assignee: "M. Alvarez",
    dueDate: "2026-05-17",
    status: "Waiting Parts",
    summary: "Seal leakage risk is increasing and spare kit is in transit from FlowCore Industrial.",
  },
  {
    id: "wo-2044",
    title: "Calibrate Cooling Skid 03 pressure transmitters",
    assetName: "Cooling Skid 03",
    priority: "Medium",
    type: "Calibration",
    requestedBy: "Utilities Supervisor",
    assignee: "J. Mercer",
    dueDate: "2026-05-22",
    status: "Open",
    summary: "Quarterly calibration due for dual pressure transmitters and flow interlock verification.",
  },
  {
    id: "wo-2045",
    title: "Inspect Conveyor 11 motor fan shroud",
    assetName: "Conveyor 11",
    priority: "Low",
    type: "Inspection",
    requestedBy: "Packaging Lead",
    assignee: "T. Monroe",
    dueDate: "2026-05-20",
    status: "Open",
    summary: "Thermal trend suggests reduced airflow near the motor housing during second shift.",
  },
  {
    id: "wo-2046",
    title: "Analyze Drive 21 harmonic distortion event",
    assetName: "Drive 21",
    priority: "High",
    type: "Diagnostic",
    requestedBy: "Controls Engineer",
    assignee: "E. Ruiz",
    dueDate: "2026-05-18",
    status: "In Progress",
    summary: "Momentary bus instability was observed during a synchronized startup sequence on blend hall equipment.",
  },
  {
    id: "wo-2047",
    title: "Shutdown service for Compressor 22 oil separator",
    assetName: "Compressor 22",
    priority: "High",
    type: "Shutdown",
    requestedBy: "Maintenance Planner",
    assignee: "R. Singh",
    dueDate: "2026-05-24",
    status: "Open",
    summary: "Separator differential pressure is trending upward and requires planned downtime replacement.",
  },
];

const INITIAL_DEFECTS = [
  {
    id: "df-301",
    assetName: "Pump 04",
    defectCode: "SEAL-LEAK",
    severity: "High",
    status: "Observed",
    discoveredOn: "2026-05-14",
    description: "Pressure oscillation suggests possible valve leak or seal degradation.",
    owner: "Inspection Team",
  },
  {
    id: "df-302",
    assetName: "Compressor 17",
    defectCode: "BRG-WEAR",
    severity: "Critical",
    status: "Mitigation Planned",
    discoveredOn: "2026-05-15",
    description: "Bearing wear pattern detected from temperature and vibration alignment.",
    owner: "Reliability Engineer",
  },
  {
    id: "df-303",
    assetName: "Motor 08",
    defectCode: "LOAD-IMBAL",
    severity: "Medium",
    status: "Under Review",
    discoveredOn: "2026-05-13",
    description: "Phase current variance indicates intermittent load imbalance during conveyor surge conditions.",
    owner: "Electrical Team",
  },
  {
    id: "df-304",
    assetName: "Conveyor 11",
    defectCode: "FAN-OBSTR",
    severity: "Medium",
    status: "Observed",
    discoveredOn: "2026-05-12",
    description: "Cooling fan shroud shows contamination buildup, reducing motor airflow during peak production.",
    owner: "Packaging Maintenance",
  },
  {
    id: "df-305",
    assetName: "Drive 21",
    defectCode: "THD-SPIKE",
    severity: "High",
    status: "Mitigation Planned",
    discoveredOn: "2026-05-16",
    description: "Short-duration harmonic distortion spike observed during synchronized startup with upstream mixer loads.",
    owner: "Controls Engineer",
  },
  {
    id: "df-306",
    assetName: "Cooling Skid 03",
    defectCode: "TX-DRIFT",
    severity: "Low",
    status: "Observed",
    discoveredOn: "2026-05-11",
    description: "Pressure transmitter pair is showing small calibration drift beyond internal tolerance band.",
    owner: "Instrumentation Team",
  },
  {
    id: "df-307",
    assetName: "Compressor 22",
    defectCode: "SEP-DP-HI",
    severity: "High",
    status: "Under Review",
    discoveredOn: "2026-05-15",
    description: "Oil separator differential pressure is elevated relative to historical baseline at comparable demand.",
    owner: "Utilities Supervisor",
  },
  {
    id: "df-308",
    assetName: "Pump 12",
    defectCode: "CAV-ONSET",
    severity: "Medium",
    status: "Resolved",
    discoveredOn: "2026-05-09",
    description: "Early cavitation signature was detected and corrected after suction strainer cleaning and line flush.",
    owner: "Process Engineer",
  },
];

const INITIAL_USERS = [
  {
    id: "user-000",
    fullName: "Yashas Chandra",
    email: "yashas@auravance.demo",
    role: "Admin",
    plantScope: "All Plants",
    status: "Active",
    lastLogin: "2026-05-16 08:45",
  },
  {
    id: "user-001",
    fullName: "Ananya Rao",
    email: "ananya.rao@auravance.example",
    role: "Admin",
    plantScope: "All Plants",
    status: "Active",
    lastLogin: "2026-05-16 08:20",
  },
  {
    id: "user-002",
    fullName: "Rahul Singh",
    email: "rahul.singh@auravance.example",
    role: "Technician",
    plantScope: "Auravance East Plant",
    status: "Active",
    lastLogin: "2026-05-16 07:54",
  },
  {
    id: "user-003",
    fullName: "Leena Patel",
    email: "leena.patel@auravance.example",
    role: "Maintenance Planner",
    plantScope: "Auravance Gulf Plant",
    status: "Pending Invite",
    lastLogin: "Never",
  },
  {
    id: "user-004",
    fullName: "Marcus Hale",
    email: "marcus.hale@auravance.example",
    role: "Reliability Engineer",
    plantScope: "Auravance East Plant",
    status: "Active",
    lastLogin: "2026-05-16 09:12",
  },
  {
    id: "user-005",
    fullName: "Elena Ruiz",
    email: "elena.ruiz@auravance.example",
    role: "Plant Manager",
    plantScope: "Auravance Midwest Plant",
    status: "Active",
    lastLogin: "2026-05-16 08:58",
  },
  {
    id: "user-006",
    fullName: "Jamal Carter",
    email: "jamal.carter@auravance.example",
    role: "Viewer",
    plantScope: "Auravance West Plant",
    status: "Active",
    lastLogin: "2026-05-15 17:41",
  },
  {
    id: "user-007",
    fullName: "Mia Alvarez",
    email: "mia.alvarez@auravance.example",
    role: "Technician",
    plantScope: "Auravance Gulf Plant",
    status: "Active",
    lastLogin: "2026-05-16 06:52",
  },
  {
    id: "user-008",
    fullName: "Chris Osei",
    email: "chris.osei@auravance.example",
    role: "Maintenance Planner",
    plantScope: "Auravance West Plant",
    status: "Suspended",
    lastLogin: "2026-05-08 11:24",
  },
];

const EMPTY_PLANT_FORM = {
  name: "",
  description: "",
  location: "",
  latitude: "",
  longitude: "",
  address: "",
  organization: "",
};

const EMPTY_EQUIPMENT_FORM = {
  equipmentNumber: "",
  name: "",
  model: EQUIPMENT_MODELS[0],
  category: EQUIPMENT_CATEGORIES[0],
  description: "",
  plantId: "",
  area: "",
  status: "Running",
  manufacturer: "",
  serialNumber: "",
  assetTag: "",
  criticality: "Medium",
  installDate: "",
  commissioningDate: "",
  maintenanceStrategy: "Predictive",
  warrantyExpiry: "",
  vendorId: "",
};

const EMPTY_VENDOR_FORM = {
  name: "",
  type: VENDOR_TYPES[0],
  contactPerson: "",
  email: "",
  phone: "",
  address: "",
  slaLevel: "",
  status: "Active",
};

const EMPTY_WORK_ORDER_FORM = {
  title: "",
  assetName: "",
  priority: "Medium",
  type: "Inspection",
  requestedBy: "",
  assignee: "",
  dueDate: "",
  status: "Open",
  summary: "",
};

const EMPTY_DEFECT_FORM = {
  assetName: "",
  defectCode: "",
  severity: "Medium",
  status: "Observed",
  discoveredOn: "",
  description: "",
  owner: "",
};

const EMPTY_USER_FORM = {
  fullName: "",
  email: "",
  role: USER_ROLES[0],
  plantScope: "All Plants",
  status: "Active",
  lastLogin: "Never",
};

function getStoredUser() {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (error) {
    console.error("Unable to parse stored session:", error);
    return null;
  }
}

function getStoredAccessToken() {
  const storedUser = getStoredUser();
  return storedUser?.token ?? "";
}

function buildSessionUser(user, token, expiresAt) {
  return {
    id: user.user_id,
    fullName: user.full_name,
    email: user.email,
    role: user.role,
    plantScope: user.plant_scope,
    status: user.status,
    lastLogin: user.last_login,
    token,
    expiresAt,
  };
}

function formatDate(value) {
  if (!value) return "No data";
  return new Date(value).toLocaleString();
}

function formatPercent(value) {
  if (typeof value !== "number") return "--";
  return `${Math.round(value * 100)}%`;
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined) return "--";
  return Number(value).toFixed(digits);
}

function statusTone(label) {
  if (label === "high-risk") return "critical";
  if (label === "warning") return "warning";
  return "healthy";
}

async function readJson(path, options) {
  const url = `${API_BASE_URL}${path}`;
  const token = getStoredAccessToken();
  const headers = new Headers(options?.headers ?? {});
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });
  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json();
      detail = payload?.detail ? ` - ${payload.detail}` : "";
    } catch {
      detail = "";
    }
    throw new Error(`Request failed: ${response.status} for ${url}${detail}`);
  }
  return response.json();
}

async function writeJson(path, method, payload) {
  return readJson(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: payload ? JSON.stringify(payload) : undefined,
  });
}

function gradientId(label) {
  const normalized = label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `fill-${normalized || "chart"}`;
}

function nextId(prefix) {
  return `${prefix}-${Math.random().toString(36).slice(2, 8)}`;
}

function buildRootCauseSymptomSummary(prediction, assetAlerts) {
  if (!prediction) {
    return "Investigate asset health drift and summarize the most likely mechanical or process issue.";
  }

  const alertSummary = assetAlerts.length
    ? assetAlerts
        .slice(0, 3)
        .map((alert) => alert.message)
        .join("; ")
    : "No active alert message was supplied.";

  return [
    `Dominant signal: ${prediction.dominant_signal}.`,
    `Anomaly label: ${prediction.anomaly_label}.`,
    `Failure probability in 72h: ${Math.round(prediction.failure_probability_72h * 100)}%.`,
    `Estimated RUL: ${formatNumber(prediction.estimated_rul_hours, 1)} hours.`,
    `Recent alerts: ${alertSummary}`,
  ].join(" ");
}

function createEmptyEquipmentForm(plants = [], vendors = []) {
  return {
    ...EMPTY_EQUIPMENT_FORM,
    plantId: plants[0]?.id ?? "",
    vendorId: vendors[0]?.id ?? "",
  };
}

function mapPlantFromApi(item) {
  return {
    id: item.plant_id,
    name: item.name,
    description: item.description,
    location: item.location,
    latitude: item.latitude,
    longitude: item.longitude,
    address: item.address,
    organization: item.organization,
  };
}

function mapPlantToApi(form, selectedId) {
  return {
    plant_id: selectedId || undefined,
    name: form.name,
    description: form.description,
    location: form.location,
    latitude: form.latitude,
    longitude: form.longitude,
    address: form.address,
    organization: form.organization,
  };
}

function mapVendorFromApi(item) {
  return {
    id: item.vendor_id,
    name: item.name,
    type: item.vendor_type,
    contactPerson: item.contact_person,
    email: item.email,
    phone: item.phone,
    address: item.address,
    slaLevel: item.sla_level,
    status: item.status,
  };
}

function mapVendorToApi(form, selectedId) {
  return {
    vendor_id: selectedId || undefined,
    name: form.name,
    vendor_type: form.type,
    contact_person: form.contactPerson,
    email: form.email,
    phone: form.phone,
    address: form.address,
    sla_level: form.slaLevel,
    status: form.status,
  };
}

function mapEquipmentFromApi(item) {
  return {
    id: item.equipment_id,
    assetId: item.asset_id ?? "",
    equipmentNumber: item.equipment_number,
    name: item.name,
    model: item.model,
    category: item.category,
    description: item.description,
    plantId: item.plant_id,
    area: item.area,
    status: item.status,
    manufacturer: item.manufacturer,
    serialNumber: item.serial_number,
    assetTag: item.asset_tag,
    criticality: item.criticality,
    installDate: item.install_date,
    commissioningDate: item.commissioning_date,
    maintenanceStrategy: item.maintenance_strategy,
    warrantyExpiry: item.warranty_expiry,
    vendorId: item.vendor_id,
  };
}

function mapEquipmentToApi(form, selectedId) {
  return {
    equipment_id: selectedId || undefined,
    asset_id: form.assetId || undefined,
    equipment_number: form.equipmentNumber,
    name: form.name,
    model: form.model,
    category: form.category,
    description: form.description,
    plant_id: form.plantId,
    area: form.area,
    status: form.status,
    manufacturer: form.manufacturer,
    serial_number: form.serialNumber,
    asset_tag: form.assetTag,
    criticality: form.criticality,
    install_date: form.installDate,
    commissioning_date: form.commissioningDate,
    maintenance_strategy: form.maintenanceStrategy,
    warranty_expiry: form.warrantyExpiry,
    vendor_id: form.vendorId,
  };
}

function mapUserFromApi(item) {
  return {
    id: item.user_id,
    fullName: item.full_name,
    email: item.email,
    role: item.role,
    plantScope: item.plant_scope,
    status: item.status,
    lastLogin: item.last_login,
  };
}

function mapUserToApi(form, selectedId) {
  return {
    user_id: selectedId || undefined,
    full_name: form.fullName,
    email: form.email,
    role: form.role,
    plant_scope: form.plantScope,
    status: form.status,
    last_login: form.lastLogin,
  };
}

function mapWorkOrderFromApi(item) {
  return {
    id: item.work_order_id,
    title: item.title,
    assetName: item.asset_name,
    priority: item.priority,
    type: item.work_type,
    requestedBy: item.requested_by,
    assignee: item.assignee,
    dueDate: item.due_date,
    status: item.status,
    summary: item.summary,
  };
}

function mapWorkOrderToApi(form, selectedId) {
  return {
    work_order_id: selectedId || undefined,
    title: form.title,
    asset_name: form.assetName,
    priority: form.priority,
    work_type: form.type,
    requested_by: form.requestedBy,
    assignee: form.assignee,
    due_date: form.dueDate,
    status: form.status,
    summary: form.summary,
  };
}

function mapDefectFromApi(item) {
  return {
    id: item.defect_id,
    assetName: item.asset_name,
    defectCode: item.defect_code,
    severity: item.severity,
    status: item.status,
    discoveredOn: item.discovered_on,
    description: item.description,
    owner: item.owner,
  };
}

function mapDefectToApi(form, selectedId) {
  return {
    defect_id: selectedId || undefined,
    asset_name: form.assetName,
    defect_code: form.defectCode,
    severity: form.severity,
    status: form.status,
    discovered_on: form.discoveredOn,
    description: form.description,
    owner: form.owner,
  };
}

function mapScheduleFromApi(item) {
  return {
    id: item.schedule_id,
    assetName: item.asset_name,
    scheduleType: item.schedule_type,
    cadence: item.cadence,
    nextDue: item.next_due,
    owner: item.owner,
    status: item.status,
  };
}

function FormField({ label, children, hint }) {
  return (
    <label className="form-field">
      <span>{label}</span>
      {children}
      {hint ? <small>{hint}</small> : null}
    </label>
  );
}

function SectionHeader({ eyebrow, title, description, action }) {
  return (
    <div className="section-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
        {description ? <p className="section-copy">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

function CrudActions({ selectedId, addLabel, createLabel, updateLabel, deleteLabel, onAdd, onDelete, onSave }) {
  return (
    <div className="form-actions crud-actions">
      <button type="button" className="secondary-button" onClick={onAdd}>
        {addLabel}
      </button>
      <button type="button" className="danger-button" onClick={onDelete} disabled={!selectedId}>
        {deleteLabel}
      </button>
      <button type="button" className="primary-button" onClick={onSave}>
        {selectedId ? updateLabel : createLabel}
      </button>
    </div>
  );
}

function LoginScreen({ form, onChange, onSubmit, error }) {
  return (
    <div className="login-shell">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />
      <section className="login-card">
        <div className="login-copy">
          <p className="eyebrow">Auravance Access</p>
          <h1>Sign in to the operations console</h1>
          <p>
            Enter your email and password to access plant operations, asset management, and reliability workflows.
          </p>
        </div>
        <form
          className="login-form"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
        >
          <FormField label="Email">
            <input
              type="email"
              value={form.email}
              onChange={(event) => onChange("email", event.target.value)}
              placeholder="name@auravance.demo"
            />
          </FormField>
          <FormField label="Password">
            <input
              type="password"
              value={form.password}
              onChange={(event) => onChange("password", event.target.value)}
              placeholder="Enter password"
            />
          </FormField>
          {error ? <div className="error-banner">{error}</div> : null}
          <button type="submit" className="primary-button login-button">
            Login
          </button>
        </form>
      </section>
    </div>
  );
}

function SideNavigation({ activeView, onSelect, currentUser, onLogout }) {
  const visibleItems = NAV_ITEMS.filter((item) => currentUser.role === "Admin" || item.id !== "users");
  const grouped = visibleItems.reduce((accumulator, item) => {
    accumulator[item.group] ??= [];
    accumulator[item.group].push(item);
    return accumulator;
  }, {});

  return (
    <aside className="asset-rail navigation-rail">
      <div>
        <div className="rail-header">
          <p className="eyebrow">Auravance Suite</p>
          <h2>Operations console</h2>
        </div>
        <div className="nav-groups">
          {Object.entries(grouped).map(([group, items]) => (
            <section key={group} className="nav-group">
              <span className="nav-group-label">{group}</span>
              <div className="asset-list">
                {items.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`asset-tile nav-tile ${activeView === item.id ? "selected" : ""}`}
                    onClick={() => onSelect(item.id)}
                  >
                    <span className="asset-name">{item.label}</span>
                    <span className="asset-meta">Module</span>
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
      <div className="user-rail-card">
        <p className="eyebrow">Logged In</p>
        <strong>{currentUser.fullName}</strong>
        <span>{currentUser.email}</span>
        <span>
          {currentUser.role} {"\u00b7"} {currentUser.plantScope}
        </span>
        <button type="button" className="secondary-button" onClick={onLogout}>
          Logout
        </button>
      </div>
    </aside>
  );
}

function StatCard({ label, value, subvalue, tone = "default" }) {
  return (
    <section className={`stat-card tone-${tone}`}>
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
      <span className="stat-subvalue">{subvalue}</span>
    </section>
  );
}

function MiniLineChart({ label, unit, values, color }) {
  const filtered = values.filter((value) => typeof value === "number");
  if (filtered.length < 2) {
    return (
      <section className="chart-card">
        <div className="chart-header">
          <h3>{label}</h3>
          <span>{unit}</span>
        </div>
        <div className="chart-empty">Waiting for more telemetry</div>
      </section>
    );
  }

  const width = 320;
  const height = 120;
  const min = Math.min(...filtered);
  const max = Math.max(...filtered);
  const range = max - min || 1;
  const fillId = gradientId(label);

  const points = filtered
    .map((value, index) => {
      const x = (index / (filtered.length - 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${x},${y}`;
    })
    .join(" ");

  const latest = filtered[filtered.length - 1];

  return (
    <section className="chart-card">
      <div className="chart-header">
        <h3>{label}</h3>
        <span>
          {formatNumber(latest)} {unit}
        </span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="sparkline" role="img" aria-label={label}>
        <defs>
          <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.28" />
            <stop offset="100%" stopColor={color} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <polyline
          fill={`url(#${fillId})`}
          stroke="transparent"
          strokeWidth="0"
          points={`0,${height} ${points} ${width},${height}`}
        />
        <polyline fill="none" stroke={color} strokeWidth="4" points={points} strokeLinecap="round" />
      </svg>
      <div className="chart-scale">
        <span>{formatNumber(min)}</span>
        <span>{formatNumber(max)}</span>
      </div>
    </section>
  );
}

function AlertList({ alerts, selectedAssetId }) {
  const assetAlerts = alerts.filter((alert) => alert.asset_id === selectedAssetId).slice(0, 6);

  return (
    <section className="panel">
      <div className="panel-header">
        <p className="eyebrow">Alerts</p>
        <h3>Operational warnings</h3>
      </div>
      {assetAlerts.length === 0 ? (
        <p className="panel-empty">No active alerts yet for this asset.</p>
      ) : (
        <div className="alert-list">
          {assetAlerts.map((alert) => (
            <article key={alert.alert_id} className={`alert-item severity-${alert.severity}`}>
              <div>
                <strong>{alert.message}</strong>
                <p>
                  {alert.severity} severity {"\u00b7"} {alert.status}
                </p>
              </div>
              <time>{formatDate(alert.created_at)}</time>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function DiagnosticsPanel({ diagnostics, loading = false, error = "" }) {
  return (
    <section className="panel diagnostics-panel">
      <div className="panel-header">
        <p className="eyebrow">Root Cause</p>
        <h3>Explainable diagnostics</h3>
      </div>
      {error ? (
        <p className="panel-empty">{error}</p>
      ) : loading ? (
        <p className="panel-empty">Running grounded root cause analysis...</p>
      ) : !diagnostics ? (
        <p className="panel-empty">Run analysis for the selected asset to load a grounded diagnosis.</p>
      ) : (
        <div className="diagnostics-stack">
          <section className="panel diagnostics-summary-panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Grounded Summary</p>
                <h3>Model-backed RCA</h3>
              </div>
              <div className="diagnostics-meta">
                <span className="status-chip confidence-chip">
                  Confidence: {diagnostics.confidence ?? "n/a"}
                </span>
                <span>{diagnostics.generation_model ?? diagnostics.generation_mode ?? "local-fallback"}</span>
              </div>
            </div>
            <p className="diagnostics-summary-copy">
              {diagnostics.grounded_summary ?? "No grounded summary returned."}
            </p>
            {diagnostics.retrieval_query ? (
              <p className="diagnostics-query">
                Retrieval query: <span>{diagnostics.retrieval_query}</span>
              </p>
            ) : null}
          </section>

          <div className="diagnostics-grid">
            <div>
              <h4>Likely causes</h4>
              <ul>
                {diagnostics.likely_causes.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4>Recommended actions</h4>
              <ul>
                {diagnostics.recommended_actions.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4>Evidence sources</h4>
              <ul>
                {diagnostics.evidence_sources.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>

          <div className="evidence-list">
            {diagnostics.evidence_snippets?.map((item) => (
              <article key={`${item.source_path}-${item.chunk_index}`} className="evidence-item">
                <div className="panel-header">
                  <div>
                    <strong>{item.title}</strong>
                    <p className="evidence-meta">
                      {item.vendor} {"\u00b7"} chunk {item.chunk_index}
                    </p>
                  </div>
                  <span className="evidence-score">Score {formatNumber(item.score, 3)}</span>
                </div>
                <p className="evidence-excerpt">{item.excerpt}</p>
                <p className="evidence-path">{item.source_path}</p>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function MonitoringScreen({
  assets,
  selectedAssetId,
  onSelectAsset,
  history,
  prediction,
  alerts,
  loading,
  error,
  lastUpdated,
}) {
  const selectedAsset = useMemo(
    () => assets.find((asset) => asset.asset_id === selectedAssetId) ?? null,
    [assets, selectedAssetId],
  );

  const latestTelemetry = history[history.length - 1] ?? null;

  return (
    <>
      <header className="hero">
        <div>
          <h1 className="eyebrow">Auravance Control Center</h1>
          <p>Industrial foresight</p>
          <p className="hero-copy">
            Live simulated telemetry, failure risk scoring, and technician-ready diagnostics from the
            FastAPI backend.
          </p>
        </div>
        <div className="hero-status">
          <div className="status-chip">
            <span className={`pulse ${prediction ? statusTone(prediction.anomaly_label) : "default"}`} />
            {prediction ? prediction.anomaly_label : "loading"}
          </div>
          <span>Last refresh {lastUpdated || "pending"}</span>
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="monitoring-layout">
        <section className="panel asset-selector-panel">
          <div className="panel-header">
            <p className="eyebrow">Observed Assets</p>
            <h3>Telemetry targets</h3>
          </div>
          <div className="asset-list">
            {assets.map((asset) => (
              <button
                key={asset.asset_id}
                type="button"
                className={`asset-tile ${selectedAssetId === asset.asset_id ? "selected" : ""}`}
                onClick={() => onSelectAsset(asset.asset_id)}
              >
                <span className="asset-name">{asset.name}</span>
                <span className="asset-meta">
                  {asset.asset_type} {"\u00b7"} {asset.plant_id} / {asset.line_id}
                </span>
              </button>
            ))}
          </div>
        </section>

        <section className="monitoring-content">
          <section className="overview-card">
            <div>
              <p className="eyebrow">Selected asset</p>
              <h2>{selectedAsset?.name ?? "Loading asset"}</h2>
              <p className="asset-summary">
                {selectedAsset
                  ? `${selectedAsset.asset_type} \u00b7 ${selectedAsset.plant_id} / ${selectedAsset.line_id}`
                  : "Connecting to backend"}
              </p>
            </div>
            <div className="overview-meta">
              <span>Latest reading: {formatDate(latestTelemetry?.timestamp)}</span>
              <span>Model: {prediction?.model_version ?? "--"}</span>
            </div>
          </section>

          <section className="stats-grid">
            <StatCard
              label="Failure probability"
              value={prediction ? formatPercent(prediction.failure_probability_72h) : "--"}
              subvalue="within the next 72 hours"
              tone={prediction ? statusTone(prediction.anomaly_label) : "default"}
            />
            <StatCard
              label="Anomaly score"
              value={prediction ? formatNumber(prediction.anomaly_score) : "--"}
              subvalue={
                prediction?.dominant_signal
                  ? `Dominant signal: ${prediction.dominant_signal}`
                  : "Waiting for inference"
              }
              tone={prediction ? statusTone(prediction.anomaly_label) : "default"}
            />
            <StatCard
              label="Estimated RUL"
              value={prediction ? `${formatNumber(prediction.estimated_rul_hours, 1)} h` : "--"}
              subvalue="remaining useful life"
            />
            <StatCard
              label="Open alerts"
              value={alerts.filter((alert) => alert.asset_id === selectedAssetId).length}
              subvalue="active for selected asset"
            />
          </section>

          <section className="stats-grid telemetry-grid">
            <StatCard
              label="Temperature"
              value={latestTelemetry ? `${formatNumber(latestTelemetry.temperature_c)} \u00b0C` : "--"}
              subvalue="thermal load"
            />
            <StatCard
              label="Vibration"
              value={latestTelemetry ? formatNumber(latestTelemetry.vibration_rms, 3) : "--"}
              subvalue="RMS vibration"
            />
            <StatCard
              label="Pressure"
              value={latestTelemetry ? `${formatNumber(latestTelemetry.pressure_bar)} bar` : "--"}
              subvalue="line stability"
            />
            <StatCard
              label="Current"
              value={latestTelemetry ? `${formatNumber(latestTelemetry.current_a)} A` : "--"}
              subvalue="electrical draw"
            />
          </section>

          <section className="chart-grid">
            <MiniLineChart
              label="Temperature Trend"
              unit="\u00b0C"
              values={history.map((point) => point.temperature_c)}
              color="#ff7a1a"
            />
            <MiniLineChart
              label="Vibration Trend"
              unit="RMS"
              values={history.map((point) => point.vibration_rms)}
              color="#ff4f6d"
            />
            <MiniLineChart
              label="Pressure Trend"
              unit="bar"
              values={history.map((point) => point.pressure_bar)}
              color="#0db8de"
            />
            <MiniLineChart
              label="Current Trend"
              unit="A"
              values={history.map((point) => point.current_a)}
              color="#ffd166"
            />
          </section>

          <section className="bottom-grid">
            <AlertList alerts={alerts} selectedAssetId={selectedAssetId} />
            <section className="panel">
              <div className="panel-header">
                <p className="eyebrow">Root Cause</p>
                <h3>Open dedicated analysis</h3>
              </div>
              <p className="panel-empty">
                Use the Root Cause Analysis screen to run the OpenAI-backed diagnosis workflow, inspect
                retrieved evidence, and review grounded maintenance actions for this asset.
              </p>
            </section>
          </section>
        </section>
      </section>

      {loading ? <div className="loading-indicator">Refreshing live telemetry...</div> : null}
    </>
  );
}

function RootCauseAnalysisScreen({
  assets,
  selectedAssetId,
  onSelectAsset,
  prediction,
  alerts,
  diagnostics,
  diagnosticsLoading,
  diagnosticsError,
  ragStatus,
  symptomSummary,
  onSymptomChange,
  onRunAnalysis,
}) {
  const selectedAsset = useMemo(
    () => assets.find((asset) => asset.asset_id === selectedAssetId) ?? null,
    [assets, selectedAssetId],
  );
  const assetAlerts = alerts.filter((alert) => alert.asset_id === selectedAssetId);
  const defaultSummary = buildRootCauseSymptomSummary(prediction, assetAlerts);

  return (
    <>
      <header className="hero">
        <div>
          <h1 className="eyebrow">Root Cause Analysis</h1>
          <p>Grounded diagnostics workspace</p>
          <p className="hero-copy">
            Run a dedicated RAG workflow over predictions, alerts, and indexed manuals to produce a
            grounded explanation with evidence-backed maintenance actions.
          </p>
        </div>
        <div className="hero-status">
          <div className="status-chip">
            <span className={`pulse ${prediction ? statusTone(prediction.anomaly_label) : "default"}`} />
            {prediction ? prediction.anomaly_label : "awaiting asset"}
          </div>
          <span>
            {ragStatus
              ? `Embeddings ${ragStatus.embedded_chunks}/${ragStatus.knowledge_chunks}`
              : "RAG status pending"}
          </span>
        </div>
      </header>

      <section className="monitoring-layout">
        <section className="panel asset-selector-panel">
          <div className="panel-header">
            <p className="eyebrow">Analysis Scope</p>
            <h3>Select asset</h3>
          </div>
          <div className="asset-list">
            {assets.map((asset) => (
              <button
                key={asset.asset_id}
                type="button"
                className={`asset-tile ${selectedAssetId === asset.asset_id ? "selected" : ""}`}
                onClick={() => onSelectAsset(asset.asset_id)}
              >
                <span className="asset-name">{asset.name}</span>
                <span className="asset-meta">
                  {asset.asset_type} {"\u00b7"} {asset.plant_id} / {asset.line_id}
                </span>
              </button>
            ))}
          </div>
        </section>

        <section className="monitoring-content">
          <section className="overview-card">
            <div>
              <p className="eyebrow">Selected asset</p>
              <h2>{selectedAsset?.name ?? "Select an asset"}</h2>
              <p className="asset-summary">
                {selectedAsset
                  ? `${selectedAsset.asset_type} \u00b7 ${selectedAsset.plant_id} / ${selectedAsset.line_id}`
                  : "Choose an asset from the left rail to start analysis."}
              </p>
            </div>
            <div className="overview-meta">
              <span>Response model: {ragStatus?.response_model ?? "--"}</span>
              <span>Embedding model: {ragStatus?.embedding_model ?? "--"}</span>
            </div>
          </section>

          <section className="stats-grid">
            <StatCard
              label="Failure probability"
              value={prediction ? formatPercent(prediction.failure_probability_72h) : "--"}
              subvalue="used in RCA context"
              tone={prediction ? statusTone(prediction.anomaly_label) : "default"}
            />
            <StatCard
              label="Dominant signal"
              value={prediction?.dominant_signal ?? "--"}
              subvalue="retrieval driver"
              tone={prediction ? statusTone(prediction.anomaly_label) : "default"}
            />
            <StatCard
              label="Embedded chunks"
              value={ragStatus ? String(ragStatus.embedded_chunks) : "--"}
              subvalue={ragStatus ? `of ${ragStatus.knowledge_chunks} indexed chunks` : "knowledge status"}
            />
            <StatCard
              label="Open alerts"
              value={String(assetAlerts.length)}
              subvalue="included in prompt context"
            />
          </section>

          <section className="panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Symptom Summary</p>
                <h3>Analysis prompt context</h3>
              </div>
              <button type="button" className="secondary-button" onClick={() => onSymptomChange(defaultSummary)}>
                Load Suggested Summary
              </button>
            </div>
            <div className="form-grid">
              <FormField label="Symptom summary">
                <textarea
                  rows={6}
                  value={symptomSummary}
                  placeholder={defaultSummary}
                  onChange={(event) => onSymptomChange(event.target.value)}
                />
              </FormField>
            </div>
            <div className="form-actions">
              <button
                type="button"
                className="primary-button"
                onClick={onRunAnalysis}
                disabled={!selectedAssetId || diagnosticsLoading}
              >
                {diagnosticsLoading ? "Running analysis..." : "Run Root Cause Analysis"}
              </button>
            </div>
          </section>

          <DiagnosticsPanel diagnostics={diagnostics} loading={diagnosticsLoading} error={diagnosticsError} />
        </section>
      </section>
    </>
  );
}

function PlantsScreen({ plants, selectedPlantId, onSelect, onDelete, form, onChange, onSave, onReset }) {
  return (
    <>
      <SectionHeader
        eyebrow="Master Data"
        title="Plant Information"
        description="Manage plant identity, location, and organizational ownership for each facility."
      />

      <section className="crud-layout">
        <section className="panel">
          <div className="panel-header">
            <p className="eyebrow">Plants</p>
            <h3>Registered facilities</h3>
          </div>
          <div className="record-list">
            {plants.map((plant) => (
              <article key={plant.id} className={`record-card ${selectedPlantId === plant.id ? "selected" : ""}`}>
                <button type="button" className="record-card-main" onClick={() => onSelect(plant.id)}>
                  <strong>{plant.name}</strong>
                  <p>{plant.location}</p>
                  <span>{plant.organization}</span>
                </button>
              </article>
            ))}
          </div>
        </section>

        <section className="panel form-panel">
          <div className="panel-header">
            <p className="eyebrow">Plant Form</p>
            <h3>{selectedPlantId ? "Edit plant" : "Add plant"}</h3>
          </div>
          <div className="form-grid">
            <FormField label="Plant Name">
              <input value={form.name} onChange={(event) => onChange("name", event.target.value)} />
            </FormField>
            <FormField label="Organization">
              <input value={form.organization} onChange={(event) => onChange("organization", event.target.value)} />
            </FormField>
            <FormField label="Location">
              <input value={form.location} onChange={(event) => onChange("location", event.target.value)} />
            </FormField>
            <FormField label="Latitude">
              <input value={form.latitude} onChange={(event) => onChange("latitude", event.target.value)} />
            </FormField>
            <FormField label="Longitude">
              <input value={form.longitude} onChange={(event) => onChange("longitude", event.target.value)} />
            </FormField>
            <FormField label="Address">
              <input value={form.address} onChange={(event) => onChange("address", event.target.value)} />
            </FormField>
            <FormField label="Description">
              <textarea rows="5" value={form.description} onChange={(event) => onChange("description", event.target.value)} />
            </FormField>
          </div>
          <CrudActions
            selectedId={selectedPlantId}
            addLabel="Add Plant"
            createLabel="Create Plant"
            updateLabel="Update Plant"
            deleteLabel="Delete Plant"
            onAdd={onReset}
            onDelete={() => onDelete(selectedPlantId)}
            onSave={onSave}
          />
        </section>
      </section>
    </>
  );
}

function EquipmentScreen({
  equipment,
  plants,
  vendors,
  selectedEquipmentId,
  onSelect,
  onDelete,
  form,
  onChange,
  onSave,
  onReset,
}) {
  const equipmentResearchNotes = [
    "Core identity: equipment number, asset tag, serial number, manufacturer, model.",
    "Operational context: plant, area, category, status, criticality, maintenance strategy.",
    "Lifecycle context: install date, commissioning date, warranty expiry, vendor or service partner.",
  ];

  return (
    <>
      <SectionHeader
        eyebrow="Master Data"
        title="Equipment Details"
        description="Capture asset identity, lifecycle, vendor, and criticality information needed for maintenance and reliability workflows."
      />

      <section className="info-strip">
        {equipmentResearchNotes.map((note) => (
          <article key={note} className="info-chip">
            {note}
          </article>
        ))}
      </section>

      <section className="crud-layout">
        <section className="panel">
          <div className="panel-header">
            <p className="eyebrow">Equipment Registry</p>
            <h3>Tracked assets</h3>
          </div>
          <div className="record-list">
            {equipment.map((item) => (
              <article key={item.id} className={`record-card ${selectedEquipmentId === item.id ? "selected" : ""}`}>
                <button type="button" className="record-card-main" onClick={() => onSelect(item.id)}>
                  <strong>{item.name}</strong>
                  <p>
                    {item.equipmentNumber} {"\u00b7"} {item.category}
                  </p>
                  <span>{item.status}</span>
                </button>
              </article>
            ))}
          </div>
        </section>

        <section className="panel form-panel">
          <div className="panel-header">
            <p className="eyebrow">Equipment Form</p>
            <h3>{selectedEquipmentId ? "Edit equipment" : "Add equipment"}</h3>
          </div>
          <div className="form-grid three-column">
            <FormField label="Equipment Number">
              <input value={form.equipmentNumber} onChange={(event) => onChange("equipmentNumber", event.target.value)} />
            </FormField>
            <FormField label="Equipment Name">
              <input value={form.name} onChange={(event) => onChange("name", event.target.value)} />
            </FormField>
            <FormField label="Equipment Model">
              <select value={form.model} onChange={(event) => onChange("model", event.target.value)}>
                {EQUIPMENT_MODELS.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Category">
              <select value={form.category} onChange={(event) => onChange("category", event.target.value)}>
                {EQUIPMENT_CATEGORIES.map((category) => (
                  <option key={category} value={category}>
                    {category}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Status">
              <select value={form.status} onChange={(event) => onChange("status", event.target.value)}>
                {["Running", "Warning", "Maintenance Due", "Out of Service", "Planned Shutdown"].map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Criticality">
              <select value={form.criticality} onChange={(event) => onChange("criticality", event.target.value)}>
                {["Low", "Medium", "High", "Critical"].map((criticality) => (
                  <option key={criticality} value={criticality}>
                    {criticality}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Plant">
              <select value={form.plantId} onChange={(event) => onChange("plantId", event.target.value)}>
                <option value="">Select Plant</option>
                {plants.map((plant) => (
                  <option key={plant.id} value={plant.id}>
                    {plant.name}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Area / Location">
              <input value={form.area} onChange={(event) => onChange("area", event.target.value)} />
            </FormField>
            <FormField label="Manufacturer">
              <input value={form.manufacturer} onChange={(event) => onChange("manufacturer", event.target.value)} />
            </FormField>
            <FormField label="Serial Number">
              <input value={form.serialNumber} onChange={(event) => onChange("serialNumber", event.target.value)} />
            </FormField>
            <FormField label="Asset Tag">
              <input value={form.assetTag} onChange={(event) => onChange("assetTag", event.target.value)} />
            </FormField>
            <FormField label="Vendor / Service Partner">
              <select value={form.vendorId} onChange={(event) => onChange("vendorId", event.target.value)}>
                <option value="">Select Vendor</option>
                {vendors.map((vendor) => (
                  <option key={vendor.id} value={vendor.id}>
                    {vendor.name}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Install Date">
              <input type="date" value={form.installDate} onChange={(event) => onChange("installDate", event.target.value)} />
            </FormField>
            <FormField label="Commissioning Date">
              <input
                type="date"
                value={form.commissioningDate}
                onChange={(event) => onChange("commissioningDate", event.target.value)}
              />
            </FormField>
            <FormField label="Warranty Expiry">
              <input type="date" value={form.warrantyExpiry} onChange={(event) => onChange("warrantyExpiry", event.target.value)} />
            </FormField>
            <FormField label="Maintenance Strategy">
              <select value={form.maintenanceStrategy} onChange={(event) => onChange("maintenanceStrategy", event.target.value)}>
                {["Predictive", "Preventive", "Condition Based", "Corrective"].map((strategy) => (
                  <option key={strategy} value={strategy}>
                    {strategy}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Description">
              <textarea rows="5" value={form.description} onChange={(event) => onChange("description", event.target.value)} />
            </FormField>
          </div>
          <CrudActions
            selectedId={selectedEquipmentId}
            addLabel="Add Equipment"
            createLabel="Create Equipment"
            updateLabel="Update Equipment"
            deleteLabel="Delete Equipment"
            onAdd={onReset}
            onDelete={() => onDelete(selectedEquipmentId)}
            onSave={onSave}
          />
        </section>
      </section>
    </>
  );
}

function VendorsScreen({ vendors, selectedVendorId, onSelect, onDelete, form, onChange, onSave, onReset }) {
  return (
    <>
      <SectionHeader
        eyebrow="Master Data"
        title="Vendor Management"
        description="Manage OEMs, service partners, and parts suppliers supporting your maintenance program."
      />

      <section className="crud-layout">
        <section className="panel">
          <div className="panel-header">
            <p className="eyebrow">Vendors</p>
            <h3>Supplier network</h3>
          </div>
          <div className="record-list">
            {vendors.map((vendor) => (
              <article key={vendor.id} className={`record-card ${selectedVendorId === vendor.id ? "selected" : ""}`}>
                <button type="button" className="record-card-main" onClick={() => onSelect(vendor.id)}>
                  <strong>{vendor.name}</strong>
                  <p>{vendor.type}</p>
                  <span>{vendor.slaLevel}</span>
                </button>
              </article>
            ))}
          </div>
        </section>

        <section className="panel form-panel">
          <div className="panel-header">
            <p className="eyebrow">Vendor Form</p>
            <h3>{selectedVendorId ? "Edit vendor" : "Add vendor"}</h3>
          </div>
          <div className="form-grid">
            <FormField label="Vendor Name">
              <input value={form.name} onChange={(event) => onChange("name", event.target.value)} />
            </FormField>
            <FormField label="Vendor Type">
              <select value={form.type} onChange={(event) => onChange("type", event.target.value)}>
                {VENDOR_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Contact Person">
              <input value={form.contactPerson} onChange={(event) => onChange("contactPerson", event.target.value)} />
            </FormField>
            <FormField label="Email">
              <input value={form.email} onChange={(event) => onChange("email", event.target.value)} />
            </FormField>
            <FormField label="Phone">
              <input value={form.phone} onChange={(event) => onChange("phone", event.target.value)} />
            </FormField>
            <FormField label="SLA Level">
              <input value={form.slaLevel} onChange={(event) => onChange("slaLevel", event.target.value)} />
            </FormField>
            <FormField label="Status">
              <select value={form.status} onChange={(event) => onChange("status", event.target.value)}>
                {["Active", "Preferred", "Onboarding", "Inactive"].map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Address">
              <textarea rows="4" value={form.address} onChange={(event) => onChange("address", event.target.value)} />
            </FormField>
          </div>
          <CrudActions
            selectedId={selectedVendorId}
            addLabel="Add Vendor"
            createLabel="Create Vendor"
            updateLabel="Update Vendor"
            deleteLabel="Delete Vendor"
            onAdd={onReset}
            onDelete={() => onDelete(selectedVendorId)}
            onSave={onSave}
          />
        </section>
      </section>
    </>
  );
}

function MaintenanceSchedulesScreen({ schedules }) {
  return (
    <>
      <SectionHeader
        eyebrow="Execution"
        title="Maintenance Schedules"
        description="View upcoming predictive, preventive, and condition-based maintenance schedules."
      />

      <section className="panel">
        <div className="data-table">
          <div className="data-table-row data-table-head">
            <span>Equipment</span>
            <span>Type</span>
            <span>Cadence</span>
            <span>Next Due</span>
            <span>Owner</span>
            <span>Status</span>
          </div>
          {schedules.map((schedule) => (
            <div key={schedule.id} className="data-table-row">
              <span>{schedule.assetName}</span>
              <span>{schedule.scheduleType}</span>
              <span>{schedule.cadence}</span>
              <span>{schedule.nextDue}</span>
              <span>{schedule.owner}</span>
              <span className={`status-badge tone-${schedule.status.toLowerCase().replace(/\s+/g, "-")}`}>
                {schedule.status}
              </span>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function WorkOrdersScreen({ workOrders, selectedWorkOrderId, onSelect, onDelete, form, onChange, onSave, onReset }) {
  return (
    <>
      <SectionHeader
        eyebrow="Execution"
        title="Work Order Management"
        description="Create, update, and track inspection, repair, and diagnostic work orders."
      />

      <section className="crud-layout">
        <section className="panel">
          <div className="panel-header">
            <p className="eyebrow">Work Orders</p>
            <h3>Open pipeline</h3>
          </div>
          <div className="record-list">
            {workOrders.map((workOrder) => (
              <article
                key={workOrder.id}
                className={`record-card ${selectedWorkOrderId === workOrder.id ? "selected" : ""}`}
              >
                <button type="button" className="record-card-main" onClick={() => onSelect(workOrder.id)}>
                  <strong>{workOrder.title}</strong>
                  <p>
                    {workOrder.assetName} {"\u00b7"} {workOrder.priority}
                  </p>
                  <span>{workOrder.status}</span>
                </button>
              </article>
            ))}
          </div>
        </section>

        <section className="panel form-panel">
          <div className="panel-header">
            <p className="eyebrow">Work Order Form</p>
            <h3>{selectedWorkOrderId ? "Edit work order" : "Add work order"}</h3>
          </div>
          <div className="form-grid">
            <FormField label="Title">
              <input value={form.title} onChange={(event) => onChange("title", event.target.value)} />
            </FormField>
            <FormField label="Equipment Name">
              <input value={form.assetName} onChange={(event) => onChange("assetName", event.target.value)} />
            </FormField>
            <FormField label="Priority">
              <select value={form.priority} onChange={(event) => onChange("priority", event.target.value)}>
                {["Low", "Medium", "High", "Critical"].map((priority) => (
                  <option key={priority} value={priority}>
                    {priority}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Type">
              <select value={form.type} onChange={(event) => onChange("type", event.target.value)}>
                {["Inspection", "Repair", "Diagnostic", "Shutdown", "Calibration"].map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Requested By">
              <input value={form.requestedBy} onChange={(event) => onChange("requestedBy", event.target.value)} />
            </FormField>
            <FormField label="Assignee">
              <input value={form.assignee} onChange={(event) => onChange("assignee", event.target.value)} />
            </FormField>
            <FormField label="Due Date">
              <input type="date" value={form.dueDate} onChange={(event) => onChange("dueDate", event.target.value)} />
            </FormField>
            <FormField label="Status">
              <select value={form.status} onChange={(event) => onChange("status", event.target.value)}>
                {["Open", "In Progress", "Waiting Parts", "Completed", "Cancelled"].map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Summary">
              <textarea rows="5" value={form.summary} onChange={(event) => onChange("summary", event.target.value)} />
            </FormField>
          </div>
          <CrudActions
            selectedId={selectedWorkOrderId}
            addLabel="Add Work Order"
            createLabel="Create Work Order"
            updateLabel="Update Work Order"
            deleteLabel="Delete Work Order"
            onAdd={onReset}
            onDelete={() => onDelete(selectedWorkOrderId)}
            onSave={onSave}
          />
        </section>
      </section>
    </>
  );
}

function DefectsScreen({ defects, selectedDefectId, onSelect, onDelete, form, onChange, onSave, onReset }) {
  return (
    <>
      <SectionHeader
        eyebrow="Execution"
        title="Defects View"
        description="Track detected defects, severity, ownership, and mitigation status."
      />

      <section className="crud-layout">
        <section className="panel">
          <div className="panel-header">
            <p className="eyebrow">Detected Defects</p>
            {/* <h3>Open defect register</h3> */}
          </div>
          <div className="record-list">
            {defects.map((defect) => (
              <article key={defect.id} className={`record-card ${selectedDefectId === defect.id ? "selected" : ""}`}>
                <button type="button" className="record-card-main" onClick={() => onSelect(defect.id)}>
                  <strong>{defect.defectCode}</strong>
                  <p>
                    {defect.assetName} {"\u00b7"} {defect.severity}
                  </p>
                  <span>
                    {defect.status} {"\u00b7"} {defect.discoveredOn}
                  </span>
                </button>
              </article>
            ))}
          </div>
        </section>

        <section className="panel form-panel">
          <div className="panel-header">
            <p className="eyebrow">Defect Form</p>
            <h3>{selectedDefectId ? "Edit defect" : "Add defect"}</h3>
          </div>
          <div className="form-grid">
            <FormField label="Asset Name">
              <input value={form.assetName} onChange={(event) => onChange("assetName", event.target.value)} />
            </FormField>
            <FormField label="Defect Code" hint="Use a short engineering identifier such as BRG-WEAR or SEAL-LEAK.">
              <input value={form.defectCode} onChange={(event) => onChange("defectCode", event.target.value)} />
            </FormField>
            <FormField label="Severity">
              <select value={form.severity} onChange={(event) => onChange("severity", event.target.value)}>
                {["Low", "Medium", "High", "Critical"].map((severity) => (
                  <option key={severity} value={severity}>
                    {severity}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Status">
              <select value={form.status} onChange={(event) => onChange("status", event.target.value)}>
                {["Observed", "Under Review", "Mitigation Planned", "Resolved", "Closed"].map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Discovered On">
              <input
                type="date"
                value={form.discoveredOn}
                onChange={(event) => onChange("discoveredOn", event.target.value)}
              />
            </FormField>
            <FormField label="Owner">
              <input value={form.owner} onChange={(event) => onChange("owner", event.target.value)} />
            </FormField>
            <FormField label="Description">
              <textarea
                rows="5"
                value={form.description}
                onChange={(event) => onChange("description", event.target.value)}
              />
            </FormField>
          </div>
          <CrudActions
            selectedId={selectedDefectId}
            addLabel="Add Defect"
            createLabel="Create Defect"
            updateLabel="Update Defect"
            deleteLabel="Delete Defect"
            onAdd={onReset}
            onDelete={() => onDelete(selectedDefectId)}
            onSave={onSave}
          />
        </section>
      </section>
    </>
  );
}

function UsersScreen({ users, selectedUserId, onSelect, onDelete, form, onChange, onSave, onReset }) {
  return (
    <>
      <SectionHeader
        eyebrow="Admin"
        title="User Management"
        description="Manage users, plant scope, and role-based access for operators, planners, and administrators."
      />

      <section className="info-strip">
        {[
          "Admin: full configuration and access control.",
          "Plant Manager and Planner: work execution and schedule ownership.",
          "Technician and Viewer: limited operational access by assigned plant scope.",
        ].map((note) => (
          <article key={note} className="info-chip">
            {note}
          </article>
        ))}
      </section>

      <section className="crud-layout">
        <section className="panel">
          <div className="panel-header">
            <p className="eyebrow">Users</p>
            <h3>Access roster</h3>
          </div>
          <div className="record-list">
            {users.map((user) => (
              <article key={user.id} className={`record-card ${selectedUserId === user.id ? "selected" : ""}`}>
                <button type="button" className="record-card-main" onClick={() => onSelect(user.id)}>
                  <strong>{user.fullName}</strong>
                  <p>
                    {user.role} {"\u00b7"} {user.plantScope}
                  </p>
                  <span>{user.status}</span>
                </button>
              </article>
            ))}
          </div>
        </section>

        <section className="panel form-panel">
          <div className="panel-header">
            <p className="eyebrow">User Form</p>
            <h3>{selectedUserId ? "Edit user" : "Add user"}</h3>
          </div>
          <div className="form-grid">
            <FormField label="Full Name">
              <input value={form.fullName} onChange={(event) => onChange("fullName", event.target.value)} />
            </FormField>
            <FormField label="Email">
              <input value={form.email} onChange={(event) => onChange("email", event.target.value)} />
            </FormField>
            <FormField label="Role">
              <select value={form.role} onChange={(event) => onChange("role", event.target.value)}>
                {USER_ROLES.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Plant Scope">
              <input value={form.plantScope} onChange={(event) => onChange("plantScope", event.target.value)} />
            </FormField>
            <FormField label="Status">
              <select value={form.status} onChange={(event) => onChange("status", event.target.value)}>
                {["Active", "Pending Invite", "Suspended"].map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Last Login">
              <input value={form.lastLogin} onChange={(event) => onChange("lastLogin", event.target.value)} />
            </FormField>
          </div>
          <CrudActions
            selectedId={selectedUserId}
            addLabel="Add User"
            createLabel="Create User"
            updateLabel="Update User"
            deleteLabel="Delete User"
            onAdd={onReset}
            onDelete={() => onDelete(selectedUserId)}
            onSave={onSave}
          />
        </section>
      </section>
    </>
  );
}

function App() {
  const [activeView, setActiveView] = useState("monitoring");
  const [currentUser, setCurrentUser] = useState(getStoredUser);
  const [loginForm, setLoginForm] = useState({
    email: "",
    password: "",
  });
  const [loginError, setLoginError] = useState("");

  const [assets, setAssets] = useState([]);
  const [selectedAssetId, setSelectedAssetId] = useState("");
  const [history, setHistory] = useState([]);
  const [prediction, setPrediction] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [diagnostics, setDiagnostics] = useState(null);
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false);
  const [diagnosticsError, setDiagnosticsError] = useState("");
  const [ragStatus, setRagStatus] = useState(null);
  const [symptomSummary, setSymptomSummary] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [masterDataError, setMasterDataError] = useState("");
  const [lastUpdated, setLastUpdated] = useState("");

  const [plants, setPlants] = useState(INITIAL_PLANTS);
  const [selectedPlantId, setSelectedPlantId] = useState(INITIAL_PLANTS[0].id);
  const [plantForm, setPlantForm] = useState(INITIAL_PLANTS[0]);

  const [vendors, setVendors] = useState(INITIAL_VENDORS);
  const [selectedVendorId, setSelectedVendorId] = useState(INITIAL_VENDORS[0].id);
  const [vendorForm, setVendorForm] = useState(INITIAL_VENDORS[0]);

  const [equipment, setEquipment] = useState(INITIAL_EQUIPMENT);
  const [selectedEquipmentId, setSelectedEquipmentId] = useState(INITIAL_EQUIPMENT[0].id);
  const [equipmentForm, setEquipmentForm] = useState(INITIAL_EQUIPMENT[0]);

  const [workOrders, setWorkOrders] = useState(INITIAL_WORK_ORDERS);
  const [selectedWorkOrderId, setSelectedWorkOrderId] = useState(INITIAL_WORK_ORDERS[0].id);
  const [workOrderForm, setWorkOrderForm] = useState(INITIAL_WORK_ORDERS[0]);

  const [schedules, setSchedules] = useState(INITIAL_SCHEDULES);

  const [defects, setDefects] = useState(INITIAL_DEFECTS);
  const [selectedDefectId, setSelectedDefectId] = useState(INITIAL_DEFECTS[0].id);
  const [defectForm, setDefectForm] = useState(INITIAL_DEFECTS[0]);

  const [users, setUsers] = useState(INITIAL_USERS);
  const [selectedUserId, setSelectedUserId] = useState(INITIAL_USERS[0].id);
  const [userForm, setUserForm] = useState(INITIAL_USERS[0]);
  const isAdmin = currentUser?.role === "Admin";

  function applySelection(items, preferredId, setSelectedIdState, setFormState, emptyValue) {
    const selected = items.find((item) => item.id === preferredId) ?? items[0] ?? null;
    setSelectedIdState(selected?.id ?? "");
    setFormState(selected ?? emptyValue);
  }

  async function loadAssetsList(preferredAssetId = "") {
    const assetRows = await readJson("/assets");
    setAssets(assetRows);
    if (assetRows.length > 0) {
      const nextAssetId = assetRows.some((item) => item.asset_id === preferredAssetId)
        ? preferredAssetId
        : assetRows[0].asset_id;
      setSelectedAssetId(nextAssetId);
    } else {
      setSelectedAssetId("");
    }
  }

  async function loadRagStatus() {
    try {
      const status = await readJson("/diagnostics/status");
      setRagStatus(status);
    } catch (requestError) {
      console.error("loadRagStatus failed:", requestError);
      setRagStatus(null);
    }
  }

  async function loadMasterData(preferred = {}) {
    try {
      const requests = [
        readJson("/plants"),
        readJson("/vendors"),
        readJson("/equipment"),
        readJson("/maintenance-schedules"),
        readJson("/work-orders"),
        readJson("/defects"),
      ];
      if (isAdmin) {
        requests.push(readJson("/users"));
      }

      const [
        plantRows,
        vendorRows,
        equipmentRows,
        scheduleRows,
        workOrderRows,
        defectRows,
        userRows = [],
      ] = await Promise.all(requests);

      const nextPlants = plantRows.map(mapPlantFromApi);
      const nextVendors = vendorRows.map(mapVendorFromApi);
      const nextEquipment = equipmentRows.map(mapEquipmentFromApi);
      const nextSchedules = scheduleRows.map(mapScheduleFromApi);
      const nextWorkOrders = workOrderRows.map(mapWorkOrderFromApi);
      const nextDefects = defectRows.map(mapDefectFromApi);
      const nextUsers = isAdmin ? userRows.map(mapUserFromApi) : [];

      setPlants(nextPlants);
      setVendors(nextVendors);
      setEquipment(nextEquipment);
      setSchedules(nextSchedules);
      setWorkOrders(nextWorkOrders);
      setDefects(nextDefects);
      if (isAdmin) {
        setUsers(nextUsers);
      }

      applySelection(nextPlants, preferred.plantId ?? selectedPlantId, setSelectedPlantId, setPlantForm, EMPTY_PLANT_FORM);
      applySelection(
        nextVendors,
        preferred.vendorId ?? selectedVendorId,
        setSelectedVendorId,
        setVendorForm,
        EMPTY_VENDOR_FORM,
      );
      applySelection(
        nextEquipment,
        preferred.equipmentId ?? selectedEquipmentId,
        setSelectedEquipmentId,
        setEquipmentForm,
        createEmptyEquipmentForm(nextPlants, nextVendors),
      );
      applySelection(
        nextWorkOrders,
        preferred.workOrderId ?? selectedWorkOrderId,
        setSelectedWorkOrderId,
        setWorkOrderForm,
        EMPTY_WORK_ORDER_FORM,
      );
      applySelection(
        nextDefects,
        preferred.defectId ?? selectedDefectId,
        setSelectedDefectId,
        setDefectForm,
        EMPTY_DEFECT_FORM,
      );
      if (isAdmin) {
        applySelection(nextUsers, preferred.userId ?? selectedUserId, setSelectedUserId, setUserForm, EMPTY_USER_FORM);
      }

      setMasterDataError("");
    } catch (requestError) {
      console.error("loadMasterData failed:", requestError);
      setMasterDataError("Unable to load backend master data. Confirm the FastAPI backend is running.");
    }
  }

  useEffect(() => {
    if (!currentUser) {
      setAssets([]);
      setSelectedAssetId("");
      return;
    }
    let ignore = false;

    async function loadAssets() {
      try {
        const assetRows = await readJson("/assets");
        if (ignore) return;
        setAssets(assetRows);
        if (assetRows.length > 0) {
          setSelectedAssetId((current) => current || assetRows[0].asset_id);
        }
      } catch (requestError) {
        console.error("loadAssets failed:", requestError);
        if (!ignore) {
          setError("Unable to load assets. Confirm the FastAPI backend is running on port 8000.");
        }
      }
    }

    loadAssets();
    return () => {
      ignore = true;
    };
  }, [currentUser]);

  useEffect(() => {
    if (!currentUser) return;
    loadMasterData();
    loadRagStatus();
  }, [currentUser, isAdmin]);

  useEffect(() => {
    if (!currentUser?.token) return;
    let cancelled = false;

    async function hydrateSession() {
      try {
        const me = await readJson("/auth/me");
        if (cancelled) return;
        const updatedUser = buildSessionUser(me, currentUser.token, currentUser.expiresAt ?? null);
        window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(updatedUser));
        setCurrentUser(updatedUser);
      } catch (requestError) {
        console.error("hydrateSession failed:", requestError);
        if (cancelled) return;
        window.localStorage.removeItem(SESSION_STORAGE_KEY);
        setCurrentUser(null);
        setLoginError("Your session expired. Sign in again.");
      }
    }

    hydrateSession();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setDiagnostics(null);
    setDiagnosticsError("");
    setSymptomSummary("");
  }, [selectedAssetId]);

  useEffect(() => {
    if (!selectedAssetId || !currentUser) return;
    let cancelled = false;

    async function loadDashboard() {
      setLoading(true);
      try {
        const [historyRows, predictionRow, alertRows] = await Promise.all([
          readJson(`/telemetry/assets/${selectedAssetId}/history?limit=24`),
          readJson(`/predictions/assets/${selectedAssetId}/latest`),
          readJson("/alerts"),
        ]);

        if (cancelled) return;
        setHistory(historyRows);
        setPrediction(predictionRow);
        setAlerts(alertRows);
        setLastUpdated(new Date().toLocaleTimeString());
        setError("");
      } catch (requestError) {
        console.error("loadDashboard failed:", requestError);
        if (!cancelled) {
          setError("Dashboard refresh failed. Check that the backend and simulator are still running.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadDashboard();
    const intervalId = window.setInterval(loadDashboard, 4000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [selectedAssetId, currentUser]);

  async function handleLogin() {
    try {
      const payload = await readJson("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: loginForm.email.trim(),
          password: loginForm.password,
        }),
      });
      const sessionUser = buildSessionUser(payload.user, payload.access_token, payload.expires_at);
      window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(sessionUser));
      setCurrentUser(sessionUser);
      setLoginError("");
    } catch (requestError) {
      console.error("handleLogin failed:", requestError);
      setLoginError(requestError?.message ?? "Invalid email or password.");
    }
  }

  function handleLogout() {
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
    setCurrentUser(null);
    setMasterDataError("");
  }

  async function performMasterDataAction(action) {
    try {
      await action();
      setMasterDataError("");
    } catch (requestError) {
      console.error("master data action failed:", requestError);
      setMasterDataError(requestError?.message ?? "Unable to save backend changes. Check the API server.");
    }
  }

  async function runRootCauseAnalysis() {
    if (!selectedAssetId) return;

    const assetAlerts = alerts.filter((alert) => alert.asset_id === selectedAssetId);
    const summary = symptomSummary.trim() || buildRootCauseSymptomSummary(prediction, assetAlerts);

    setDiagnosticsLoading(true);
    setDiagnosticsError("");

    try {
      const diagnosticsRow = await readJson("/diagnostics/root-cause", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          asset_id: selectedAssetId,
          symptom_summary: summary,
          recent_alert_ids: assetAlerts.slice(0, 5).map((alert) => alert.alert_id),
        }),
      });
      setDiagnostics(diagnosticsRow);
      await loadRagStatus();
    } catch (requestError) {
      console.error("runRootCauseAnalysis failed:", requestError);
      setDiagnostics(null);
      setDiagnosticsError(requestError?.message ?? "Unable to run root cause analysis.");
    } finally {
      setDiagnosticsLoading(false);
    }
  }

  async function savePlant() {
    const path = selectedPlantId ? `/plants/${selectedPlantId}` : "/plants";
    const method = selectedPlantId ? "PUT" : "POST";
    const response = await writeJson(path, method, mapPlantToApi(plantForm, selectedPlantId));
    await loadMasterData({ plantId: response.plant_id });
  }

  async function deletePlantRecord(id) {
    if (!id) return;
    await writeJson(`/plants/${id}`, "DELETE");
    await loadMasterData();
  }

  async function saveVendor() {
    const path = selectedVendorId ? `/vendors/${selectedVendorId}` : "/vendors";
    const method = selectedVendorId ? "PUT" : "POST";
    const response = await writeJson(path, method, mapVendorToApi(vendorForm, selectedVendorId));
    await loadMasterData({ vendorId: response.vendor_id });
  }

  async function deleteVendorRecord(id) {
    if (!id) return;
    await writeJson(`/vendors/${id}`, "DELETE");
    await loadMasterData();
  }

  async function saveEquipment() {
    const path = selectedEquipmentId ? `/equipment/${selectedEquipmentId}` : "/equipment";
    const method = selectedEquipmentId ? "PUT" : "POST";
    const response = await writeJson(path, method, mapEquipmentToApi(equipmentForm, selectedEquipmentId));
    await Promise.all([
      loadMasterData({ equipmentId: response.equipment_id }),
      loadAssetsList(response.asset_id ?? ""),
    ]);
  }

  async function deleteEquipmentRecord(id) {
    if (!id) return;
    await writeJson(`/equipment/${id}`, "DELETE");
    await Promise.all([loadMasterData(), loadAssetsList()]);
  }

  async function saveWorkOrder() {
    const path = selectedWorkOrderId ? `/work-orders/${selectedWorkOrderId}` : "/work-orders";
    const method = selectedWorkOrderId ? "PUT" : "POST";
    const response = await writeJson(path, method, mapWorkOrderToApi(workOrderForm, selectedWorkOrderId));
    await loadMasterData({ workOrderId: response.work_order_id });
  }

  async function deleteWorkOrderRecord(id) {
    if (!id) return;
    await writeJson(`/work-orders/${id}`, "DELETE");
    await loadMasterData();
  }

  async function saveDefect() {
    const path = selectedDefectId ? `/defects/${selectedDefectId}` : "/defects";
    const method = selectedDefectId ? "PUT" : "POST";
    const response = await writeJson(path, method, mapDefectToApi(defectForm, selectedDefectId));
    await loadMasterData({ defectId: response.defect_id });
  }

  async function deleteDefectRecord(id) {
    if (!id) return;
    await writeJson(`/defects/${id}`, "DELETE");
    await loadMasterData();
  }

  async function saveUser() {
    const path = selectedUserId ? `/users/${selectedUserId}` : "/users";
    const method = selectedUserId ? "PUT" : "POST";
    const response = await writeJson(path, method, mapUserToApi(userForm, selectedUserId));
    await loadMasterData({ userId: response.user_id });
  }

  async function deleteUserRecord(id) {
    if (!id) return;
    await writeJson(`/users/${id}`, "DELETE");
    await loadMasterData();
  }

  function renderActiveScreen() {
    switch (activeView) {
      case "plants":
        return (
          <PlantsScreen
            plants={plants}
            selectedPlantId={selectedPlantId}
            onSelect={(id) => {
              const plant = plants.find((item) => item.id === id);
              setSelectedPlantId(id);
              setPlantForm(plant ?? EMPTY_PLANT_FORM);
            }}
            onDelete={(id) => performMasterDataAction(() => deletePlantRecord(id))}
            form={plantForm}
            onChange={(field, value) => setPlantForm((current) => ({ ...current, [field]: value }))}
            onSave={() => performMasterDataAction(savePlant)}
            onReset={() => {
              setSelectedPlantId("");
              setPlantForm(EMPTY_PLANT_FORM);
            }}
          />
        );
      case "equipment":
        return (
          <EquipmentScreen
            equipment={equipment}
            plants={plants}
            vendors={vendors}
            selectedEquipmentId={selectedEquipmentId}
            onSelect={(id) => {
              const item = equipment.find((entry) => entry.id === id);
              setSelectedEquipmentId(id);
              setEquipmentForm(item ?? EMPTY_EQUIPMENT_FORM);
            }}
            onDelete={(id) => performMasterDataAction(() => deleteEquipmentRecord(id))}
            form={equipmentForm}
            onChange={(field, value) => setEquipmentForm((current) => ({ ...current, [field]: value }))}
            onSave={() => performMasterDataAction(saveEquipment)}
            onReset={() => {
              setSelectedEquipmentId("");
              setEquipmentForm(createEmptyEquipmentForm(plants, vendors));
            }}
          />
        );
      case "vendors":
        return (
          <VendorsScreen
            vendors={vendors}
            selectedVendorId={selectedVendorId}
            onSelect={(id) => {
              const item = vendors.find((entry) => entry.id === id);
              setSelectedVendorId(id);
              setVendorForm(item ?? EMPTY_VENDOR_FORM);
            }}
            onDelete={(id) => performMasterDataAction(() => deleteVendorRecord(id))}
            form={vendorForm}
            onChange={(field, value) => setVendorForm((current) => ({ ...current, [field]: value }))}
            onSave={() => performMasterDataAction(saveVendor)}
            onReset={() => {
              setSelectedVendorId("");
              setVendorForm(EMPTY_VENDOR_FORM);
            }}
          />
        );
      case "schedules":
        return <MaintenanceSchedulesScreen schedules={schedules} />;
      case "workorders":
        return (
          <WorkOrdersScreen
            workOrders={workOrders}
            selectedWorkOrderId={selectedWorkOrderId}
            onSelect={(id) => {
              const item = workOrders.find((entry) => entry.id === id);
              setSelectedWorkOrderId(id);
              setWorkOrderForm(item ?? EMPTY_WORK_ORDER_FORM);
            }}
            onDelete={(id) => performMasterDataAction(() => deleteWorkOrderRecord(id))}
            form={workOrderForm}
            onChange={(field, value) => setWorkOrderForm((current) => ({ ...current, [field]: value }))}
            onSave={() => performMasterDataAction(saveWorkOrder)}
            onReset={() => {
              setSelectedWorkOrderId("");
              setWorkOrderForm(EMPTY_WORK_ORDER_FORM);
            }}
          />
        );
      case "defects":
        return (
          <DefectsScreen
            defects={defects}
            selectedDefectId={selectedDefectId}
            onSelect={(id) => {
              const item = defects.find((entry) => entry.id === id);
              setSelectedDefectId(id);
              setDefectForm(item ?? EMPTY_DEFECT_FORM);
            }}
            onDelete={(id) => performMasterDataAction(() => deleteDefectRecord(id))}
            form={defectForm}
            onChange={(field, value) => setDefectForm((current) => ({ ...current, [field]: value }))}
            onSave={() => performMasterDataAction(saveDefect)}
            onReset={() => {
              setSelectedDefectId("");
              setDefectForm(EMPTY_DEFECT_FORM);
            }}
          />
        );
      case "users":
        return (
          <UsersScreen
            users={users}
            selectedUserId={selectedUserId}
            onSelect={(id) => {
              const item = users.find((entry) => entry.id === id);
              setSelectedUserId(id);
              setUserForm(item ?? EMPTY_USER_FORM);
            }}
            onDelete={(id) => performMasterDataAction(() => deleteUserRecord(id))}
            form={userForm}
            onChange={(field, value) => setUserForm((current) => ({ ...current, [field]: value }))}
            onSave={() => performMasterDataAction(saveUser)}
            onReset={() => {
              setSelectedUserId("");
              setUserForm(EMPTY_USER_FORM);
            }}
          />
        );
      case "rootcause":
        return (
          <RootCauseAnalysisScreen
            assets={assets}
            selectedAssetId={selectedAssetId}
            onSelectAsset={setSelectedAssetId}
            prediction={prediction}
            alerts={alerts}
            diagnostics={diagnostics}
            diagnosticsLoading={diagnosticsLoading}
            diagnosticsError={diagnosticsError}
            ragStatus={ragStatus}
            symptomSummary={symptomSummary}
            onSymptomChange={setSymptomSummary}
            onRunAnalysis={runRootCauseAnalysis}
          />
        );
      case "monitoring":
      default:
        return (
          <MonitoringScreen
            assets={assets}
            selectedAssetId={selectedAssetId}
            onSelectAsset={setSelectedAssetId}
            history={history}
            prediction={prediction}
            alerts={alerts}
            loading={loading}
            error={error}
            lastUpdated={lastUpdated}
          />
        );
    }
  }

  if (!currentUser) {
    return (
      <LoginScreen
        form={loginForm}
        onChange={(field, value) => {
          setLoginForm((current) => ({ ...current, [field]: value }));
          setLoginError("");
        }}
        onSubmit={handleLogin}
        error={loginError}
      />
    );
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />
      <SideNavigation activeView={activeView} onSelect={setActiveView} currentUser={currentUser} onLogout={handleLogout} />
      <main className="dashboard module-dashboard">
        {masterDataError ? <div className="error-banner">{masterDataError}</div> : null}
        {renderActiveScreen()}
      </main>
    </div>
  );
}

export default App;
