# kasaExporter

python-kasa-based shim exporter for Kasa KP115 plugs on firmware 1.1.1 (KLAP
protocol, flaky device-side handshake — retried per poll). Replaces
`rebelcore/kasa-exporter` and emits the same metric names on `:9498`:

- `kasa_device_up{alias,host}`
- `kasa_power_watts`, `kasa_current_amperes`, `kasa_voltage_volts`
- `kasa_energy_kilowatt_hours_total`
- `kasa_device_signal_strength_dbm`
- `kasa_device_info{alias,host,model,device_id,firmware_version,mac}`
- optional: `kasa_device_led_on`, `kasa_device_uptime_seconds`

## Configuration (env)

| Variable | Default | Meaning |
|---|---|---|
| `KASA_USERNAME` / `KASA_PASSWORD` | — | Kasa cloud credentials (KLAP auth) |
| `KASA_HOSTS` | — | Comma-separated plug IPs (or `--kasa.address=a,b,...` arg) |
| `KASA_PORT` | `9498` | Metrics listen port |
| `KASA_POLL_INTERVAL` | `10` | Seconds between poll cycles |
| `KASA_RETRIES` | `4` | Auth attempts per host per cycle |
| `KASA_RETRY_DELAY` | `2` | Seconds between retries |

Read-only: the exporter never issues power-control commands.

Image: `ghcr.io/taoofshawn/kasaexporter` (date tags `YYYYmmdd_HHMM` + `latest`).
