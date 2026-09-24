APP_NAME = "Mogged VPN"
APP_VERSION = "1.1.0"
APP_MUTEX_NAME = "Global\\MoggedVPN_SingleInstance"

APP_WIDTH = 1024
APP_HEIGHT = 580

STATUS_DISCONNECTED = "DISCONNECTED"
STATUS_CONNECTING = "CONNECTING"
STATUS_CONNECTED = "CONNECTED"
STATUS_ERROR = "ERROR"

MODE_FULL = "full"
MODE_DISCORD = "discord"

VPN_GATE_API_URLS = [
    "https://www.vpngate.net/api/iphone/",
]

OPENVPN_PROVIDERS = [
    {
        "name": "vpngate",
        "url": "https://www.vpngate.net/api/iphone/",
        "parser": "vpngate",
        "priority": 1,
    },
    {
        "name": "vpngate_udp",
        "url": "https://raw.githubusercontent.com/hoang-rio/vpn-gate-openvpn-udp/refs/heads/master/vpn_servers.csv",
        "parser": "vpngate",
        "priority": 2,
    },
    {
        "name": "auto_ovpn",
        "url": "https://api.github.com/repos/9xN/auto-ovpn/git/trees/main?recursive=1",
        "parser": "auto_ovpn",
        "priority": 3,
    },
]

CONNECT_TIMEOUT_SEC = 25.0
HANDSHAKE_WINDOW_SEC = 20
SERVER_FETCH_TIMEOUT_SEC = 15.0
DISCORD_GRACEFUL_TIMEOUT_SEC = 5.0
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0

EXPECTED_BINARIES = {
    "openvpn.exe": "OpenVPN Technologies, Inc.",
    "wintun.dll": "WireGuard LLC",
}
