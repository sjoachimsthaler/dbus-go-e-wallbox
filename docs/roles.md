# Available Roles

Victron Venus OS uses **roles** to categorise each device on the D-Bus. The role determines how system calc interprets the device's data (PV production vs grid import vs charging, etc.).

## AC / Power Device Roles

| Role | Description | Suitable for a go-eCharger wallbox? |
|------|---------------|----------------------|
| **`evcharger`** | EV charging stations – wallboxes, smart cables | ✅ **Yes – this is the correct role** |
| `acchargecable` | EV charging cables (legacy) | △ Partial – older plugins use this |
| `energymeter` | Energy meters | △ Partial – lacks charging-specific status |
| `charger` | AC battery chargers (e.g. Wallbox Charger, Blue Phoenix) | ❌ No – makes Venus OS think you're charging batteries |
| `grid` | Grid / network connection points | ❌ No – would mess up import/export calculations |
| `inverter` | DC→AC inverters | ❌ No |
| `invertercharger` | Combined inverter + charger (e.g. MultiPlus) | ❌ No |
| `pvinverter` | Solar PV inverters | ❌ No |
| `generator` | Generators | ❌ No |
| `dc2dc` | DC-DC converters | ❌ No |

## Why `evcharger`?

`evcharger` is the **official Victron role for all EV charging stations** including wallboxes and smart cables. The D-Bus spec defines specific paths for EV chargers that other roles don't support:

```
com.victronenergy.evcharger
├── /Ac/Energy/Forward          <-- Total energy consumed (kWh)
├── /Ac/L1/Power                <-- L1 Power used (W)
├── /Ac/L2/Power                <-- L2 Power used (W)
├── /Ac/L3/Power                <-- L3 Power used (W)
├── /Ac/Power                   <-- AC Power total (W)
├── /AutoStart                  <-- 0=disabled, 1=enabled
├── /Connected                  <-- Car connection state
├── /Current                    <-- Actual charging current (A)
├── /MaxCurrent                 <-- Maximum allowed current (A)
├── /Mode                       <-- 0=Manual, 1=Auto
├── /Position                   <-- 0=AC Output, 1=AC Input
├── /SetCurrent                 <-- Charge current setpoint (A)
├── /Session/Time               <-- Session charging time (seconds)
├── /Session/Energy             <-- Session charging energy (kWh)
├── /Session/Cost               <-- Session cost
├── /Status                     <-- 0=disconnected, 1=connected, 2=charging, 3=charged, 4=waiting for sun, 5=waiting for RFID, 6=waiting for start, ...
└── ...
```

Using this role:
- System calc correctly recognises the device as an EV charger
- Power values are interpreted as charging load (consumption from the grid/inverter)
- Energy totals track consumption only (no reverse/export)
- The device appears under "EV Chargers" in VictronConnect and the Venus GX dashboard

## Data Available from go-eCharger

The go-eCharger REST API v2 provides the following data points:

| D-Bus Path | API Source | Available |
|-----------|------------|-----------|
| `/Ac/L1/L2/L3/Voltage` | `nrg.U` | ✅ Yes |
| `/Ac/L1/L2/L3/Current` | `nrg.I` | ✅ Yes |
| `/Ac/L1/L2/L3/Power` | `nrg.P` | ✅ Yes |
| `/Ac/Power` | `nrg.P[4]` | ✅ Yes |
| `/Ac/Energy/Forward` | `eto` | ✅ Yes |
| `/Connected` | `carconn` | ✅ Yes |
| `/Status` | Derived from `carconn` + `current` | ✅ Yes |
| `/Current` | `current` | ✅ Yes |
| `/Session/Energy` | `se` | ✅ Yes |
| `/Session/Time` | Not available | ❌ Set to 0 |
| `/Session/Cost` | Not available | ❌ Not supported |
| `/SetCurrent` | Not available | ❌ Not supported |
| `/MaxCurrent` | Not available | ❌ Not supported |

## Custom Display Name

Set `CustomName` in [`config.ini`](../config.ini) to whatever you prefer – e.g. `"go-e Wallbox"` or `"Gemini Flex"`. This is what shows up in the UI regardless of the underlying role.

## References
- https://github.com/victronenergy/venus/wiki/dbus#evcharger – Official evcharger role definition
- https://github.com/victronenergy/venus/wiki/dbus-api – D-Bus API
- https://github.com/goecharger/go-eCharger-API-v2 – go-eCharger API v2 documentation
