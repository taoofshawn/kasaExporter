#!/usr/bin/env python3
"""Kasa exporter shim — python-kasa based replacement for rebelcore/kasa-exporter.

Why: KP115 firmware 1.1.1 dropped the legacy TCP-9999 protocol (CVE-2026-76784)
and speaks KLAP on port 80 with a flaky device-side handshake (~55% per-attempt
acceptance). This exporter polls each host with retries and emits the SAME
metric names the existing Grafana dashboard already queries, so the dashboard
and the Prometheus job label (kasa-exporter) need no changes.

Read-only: never calls any power-controlling operation.
"""

import asyncio
import logging
import os
import sys
import time

from kasa import Credentials, Discover
from prometheus_client import Gauge, start_http_server

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("kasa-exporter")

LISTEN_PORT = int(os.environ.get("KASA_PORT", "9498"))
POLL_INTERVAL = int(os.environ.get("KASA_POLL_INTERVAL", "10"))
RETRIES = int(os.environ.get("KASA_RETRIES", "4"))
RETRY_DELAY = float(os.environ.get("KASA_RETRY_DELAY", "2"))
USERNAME = os.environ.get("KASA_USERNAME", "")
PASSWORD = os.environ.get("KASA_PASSWORD", "")


def hosts_from_argv():
    """Extract --kasa.address=a,b,c,d from args; tolerate unknown legacy flags."""
    for arg in sys.argv[1:]:
        if arg.startswith("--kasa.address="):
            hosts = [h for h in arg.split("=", 1)[1].split(",") if h]
            if hosts:
                return hosts
    env = os.environ.get("KASA_HOSTS", "")
    return [h for h in env.split(",") if h]


HOSTS = hosts_from_argv()
if not HOSTS:
    log.error("no hosts: pass --kasa.address=a,b,c,... or set KASA_HOSTS")
    sys.exit(1)

UP = Gauge("kasa_device_up", "Device reachable and polled successfully", ["alias", "host"])
POWER = Gauge("kasa_power_watts", "Current power draw in watts", ["alias", "host"])
CURRENT = Gauge("kasa_current_amperes", "Current in amperes", ["alias", "host"])
VOLTAGE = Gauge("kasa_voltage_volts", "Voltage in volts", ["alias", "host"])
ENERGY = Gauge("kasa_energy_kilowatt_hours_total", "Total energy in kWh", ["alias", "host"])
RSSI = Gauge("kasa_device_signal_strength_dbm", "WiFi signal strength in dBm", ["alias", "host"])
INFO = Gauge(
    "kasa_device_info",
    "Device metadata (always 1 when up)",
    ["alias", "host", "model", "device_id", "firmware_version", "mac"],
)
LED = Gauge("kasa_device_led_on", "LED state (1=on)", ["alias", "host"])
UPTIME = Gauge("kasa_device_uptime_seconds", "Device uptime in seconds", ["alias", "host"])


async def poll_host(host):
    creds = Credentials(USERNAME, PASSWORD)
    for attempt in range(1, RETRIES + 1):
        try:
            dev = await Discover.discover_single(host, credentials=creds)
            await dev.update()
            break
        except Exception as e:
            log.warning("host %s attempt %d/%d failed: %s: %s",
                        host, attempt, RETRIES, type(e).__name__, str(e)[:120])
            if attempt < RETRIES:
                await asyncio.sleep(RETRY_DELAY)
    else:
        UP.labels(alias="unknown", host=host).set(0)
        log.error("host %s unreachable after %d attempts", host, RETRIES)
        return

    info = dev.sys_info or {}
    alias = dev.alias or host
    device_id = info.get("deviceId") or info.get("device_id") or ""
    mac = info.get("mac") or info.get("macAddr") or ""
    model = info.get("model") or ""
    fw = info.get("fwVer") or info.get("fw_ver") or ""

    UP.labels(alias=alias, host=host).set(1)
    INFO.labels(alias=alias, host=host, model=model, device_id=device_id,
                firmware_version=fw, mac=mac).set(1)

    rt = getattr(dev, "emeter_realtime", None)
    if rt is not None:
        power = getattr(rt, "power", None)
        current = getattr(rt, "current", None)
        voltage = getattr(rt, "voltage", None)
        total = getattr(rt, "total", None)
        if power is not None:
            POWER.labels(alias=alias, host=host).set(float(power))
        if current is not None:
            CURRENT.labels(alias=alias, host=host).set(float(current))
        if voltage is not None:
            VOLTAGE.labels(alias=alias, host=host).set(float(voltage))
        if total is not None:
            ENERGY.labels(alias=alias, host=host).set(float(total))

    rssi = info.get("rssi")
    if rssi is not None:
        RSSI.labels(alias=alias, host=host).set(float(rssi))
    on_time = info.get("on_time")
    if on_time is not None:
        UPTIME.labels(alias=alias, host=host).set(float(on_time))
    led = info.get("led_state") if "led_state" in info else None
    if led is not None and isinstance(led, dict):
        led = led.get("led_state")
    if led is not None:
        LED.labels(alias=alias, host=host).set(1 if led else 0)

    log.info("host %s (%s): power=%s W rssi=%s", host, alias,
             getattr(rt, "power", None) if rt else None, rssi)


async def main():
    start_http_server(LISTEN_PORT)
    log.info("listening on :%d, polling %s every %ds (retries=%d)",
             LISTEN_PORT, HOSTS, POLL_INTERVAL, RETRIES)
    while True:
        for host in HOSTS:
            await poll_host(host)
        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
