#!/usr/bin/env bash
set -euo pipefail

log(){ printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }

if [ ! -e /dev/net/tun ]; then
  log "ERROR: /dev/net/tun missing. Add device or privileged mode. Sleeping."; sleep 3600; exit 1; fi

# Optional (some nordvpn components expect dbus)
if [ ! -S /var/run/dbus/system_bus_socket ]; then
  mkdir -p /var/run/dbus; dbus-daemon --system --fork || true; fi

TOKEN=${TOKEN:?Need NORDVPN token (env NORDVPN_TOKEN)}
CONNECT=${CONNECT:?Need country code (env CONNECT_COUNTRY)}

retry(){
  local tries=$1; shift; local sleep_sec=$1; shift; local i
  for i in $(seq 1 "$tries"); do
    if "$@"; then return 0; fi
    log "[retry] $i/$tries failed: $*"; sleep "$sleep_sec"; done; return 1; }

log "Starting nordvpn service script"
/etc/init.d/nordvpn start || { log "Failed to start /etc/init.d/nordvpn"; sleep 10; }

# Wait for daemon socket
for i in $(seq 1 30); do
  [ -S /run/nordvpn/nordvpnd.sock ] && break
  sleep 1
  if [ "$i" = 30 ]; then log "Daemon socket not ready"; fi
done

log "Logging in (non-interactive, auto answering analytics = no)"
retry 12 2 bash -lc 'yes n | nordvpn login --token '"$TOKEN"'' || log "WARNING: login failed after retries"

# Configure (best effort)
retry 5 2 nordvpn set analytics off || true
retry 5 2 nordvpn set technology nordlynx || true
retry 5 2 nordvpn set killswitch on || true
retry 5 2 nordvpn whitelist add subnet 172.17.0.0/16 || true

log "Connecting to $CONNECT"
retry 20 4 nordvpn connect "$CONNECT" || log "ERROR: connect failed"

log "Startup complete. Monitoring status." 
while true; do nordvpn status || true; sleep 30; done
