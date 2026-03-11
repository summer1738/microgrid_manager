# User Registration & System Packages — System Design

This document structures user registration and system packages for the microgrid management system. Use it in your system design chapter or report.

---

## 1. Why User Registration is Needed

User registration allows the system to:

- **Identify** who is using the system
- **Assign** the correct microgrid package
- **Configure** the system based on energy setup
- **Manage** different system scales

Without registration, the system cannot adapt to different setups.

### Example: User → System Type

| User        | System type      |
|------------|------------------|
| Household  | Small solar system |
| Clinic     | Medium microgrid   |
| Business park | Large microgrid |

---

## 2. System Packages

Three system packages are defined.

### Package 1: Household Package

**For:** Single homes with small solar systems.

| Aspect | Description |
|--------|-------------|
| **Typical setup** | 1 house, small PV (1–5 kW), small battery, few appliances |
| **System features** | PV forecasting, battery charge monitoring, energy usage dashboard |

### Package 2: Community Microgrid Package

**For:** Multiple homes or small businesses.

| Aspect | Description |
|--------|-------------|
| **Typical setup** | 3–10 homes, shared solar, shared battery storage |
| **System features** | Load sharing, energy allocation, forecasting for multiple users, consumption monitoring |

### Package 3: Institutional / Critical Facility Package

**For:** Clinics, schools, or businesses.

| Aspect | Description |
|--------|-------------|
| **Typical setup** | Clinic microgrid, school microgrid, rural business center |
| **System features** | Priority load management, energy scheduling, reliability monitoring, backup power management |
| **Example priority loads** | Medical equipment, refrigeration, lighting |

---

## 3. Registration Process

### Step 1 — User creates account

**Information collected:**

- Name  
- Email  
- Password  
- Location  

### Step 2 — Choose system type

**Options:**

1. Household Solar System  
2. Community Microgrid  
3. Institutional Microgrid  

### Step 3 — Enter system details

**Example inputs:**

- Number of houses (for community)  
- PV capacity (kW)  
- Battery capacity (kWh)  
- Critical loads  

### Step 4 — System configures dashboard

Depending on package, the system enables features as follows.

| Feature | Household | Community | Institutional |
|---------|:---------:|:---------:|:--------------:|
| PV forecasting | ✓ | ✓ | ✓ |
| Battery control | ✓ | ✓ | ✓ |
| Load prioritization | ✗ | ✓ | ✓ |
| Multi-user management | ✗ | ✓ | ✓ |

---

## 4. Database Structure

### Users

| Column | Description |
|--------|-------------|
| `user_id` | Primary key |
| `name` | User name |
| `email` | Email (login) |
| `password` | Hashed password |
| `system_type` | 1=Household, 2=Community, 3=Institutional |
| `location` | Geographic/location identifier |

### Microgrid_Setup

| Column | Description |
|--------|-------------|
| `setup_id` | Primary key |
| `user_id` | Foreign key → Users |
| `pv_capacity` | PV capacity (kW) |
| `battery_capacity` | Battery capacity (kWh) |
| `number_of_buildings` | For community/institutional |
| `critical_load` | Critical load description or list |

---

## 5. How This Helps the AI Model

The forecasting and control system can adapt to the setup.

| Package | AI / system behaviour |
|---------|------------------------|
| **Household** | Forecast PV → manage battery → supply home |
| **Community microgrid** | Forecast PV → distribute power to houses |
| **Institutional (e.g. clinic)** | Forecast PV → prioritize medical equipment and critical loads |

---

## 6. Scalability (Project strength)

This design introduces **scalability**: the same system can support

- Small solar systems (household)  
- Medium microgrids (community)  
- Large community or institutional systems  

This is strong system design for a single, adaptable microgrid management platform.
