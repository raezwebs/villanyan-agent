"""Villanyan-Agent 3.0 — Network routes (port listing)."""

import os
import re
import subprocess

from fastapi import APIRouter, Depends, HTTPException

from backend.core.models import User
from backend.core.security import get_current_user

router = APIRouter(prefix="/api/network", tags=["network"])


def _parse_proc_net_tcp() -> list[dict]:
    """Parse /proc/net/tcp for listening ports."""
    ports = []
    try:
        with open("/proc/net/tcp") as f:
            # Skip header
            next(f)
            for line in f:
                parts = line.strip().split()
                if len(parts) < 4:
                    continue
                # local_address is column 2: format 00000000:0016
                local = parts[1]
                st = int(parts[3], 16)  # TCP state
                # 0A = TCP_LISTEN = 10
                if st != 10:
                    continue
                addr_part, port_part = local.split(":")
                port = int(port_part, 16)
                inode = parts[9] if len(parts) > 9 else ""
                ports.append({
                    "port": port,
                    "protocol": "tcp",
                    "inode": inode,
                })
    except (FileNotFoundError, PermissionError, OSError):
        pass

    # Deduplicate by port
    seen = set()
    unique = []
    for p in ports:
        if p["port"] not in seen:
            seen.add(p["port"])
            unique.append(p)
    return unique


def _parse_ss_output() -> list[dict]:
    """Parse ss -tlnp output."""
    ports = []
    try:
        result = subprocess.run(
            ["ss", "-tlnp"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return _parse_proc_net_tcp()

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("State") or line.startswith("Netid"):
                continue
            # Netid  Recv-Q  Send-Q  Local Address:Port  Peer Address:Port  Process
            parts = line.split()
            if len(parts) < 4:
                continue
            local = parts[3]
            if ":" not in local:
                continue
            # Handle IPv6: [::]:port or IPv4: ip:port
            if "[" in local:
                # IPv6: [::]:443 or [::1]:80
                port_str = local.split("]:")[-1]
            else:
                port_str = local.split(":")[-1]

            try:
                port = int(port_str)
            except ValueError:
                continue

            process_info = ""
            if len(parts) >= 5:
                process_info = parts[4] if "users:" in parts[4] else ""

            ports.append({
                "port": port,
                "protocol": "tcp",
                "local": local,
                "process": process_info,
            })
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return _parse_proc_net_tcp()

    return ports


@router.get("/ports")
async def list_ports(user: User = Depends(get_current_user)):
    """List all listening TCP ports."""
    ports = _parse_ss_output()

    # Also get UDP listening ports
    udp_ports = []
    try:
        result = subprocess.run(
            ["ss", "-ulnp"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith("State") or line.startswith("Netid"):
                    continue
                parts = line.split()
                if len(parts) < 4:
                    continue
                local = parts[3]
                if ":" not in local:
                    continue
                if "[" in local:
                    port_str = local.split("]:")[-1]
                else:
                    port_str = local.split(":")[-1]
                try:
                    port = int(port_str)
                except ValueError:
                    continue
                udp_ports.append({
                    "port": port,
                    "protocol": "udp",
                    "local": local,
                })
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return {
        "tcp": ports,
        "udp": udp_ports,
        "total_tcp": len(ports),
        "total_udp": len(udp_ports),
    }
