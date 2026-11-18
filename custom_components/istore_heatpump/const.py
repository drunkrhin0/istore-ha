DOMAIN = "istore_heatpump"
MANUFACTURER = "iStore"
CONFIG_PAGE = "https://home.istore.net.au/"

# Config entry keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_ACCESS_TOKEN = "access_token"
CONF_PARENT_ID = "parent_id"
CONF_MDM_ID = "mdm_id"

# iStore R290 tank capacity (liters)
TANK_VOLUME_L = 270

# Seconds to wait for iStore cloud API to propagate commands
# before refreshing sensor state (API latency is ~15s)
COMMAND_REFRESH_DELAY = 12

# Consecutive failed polls (30 s each) before entities go unavailable. A single bad
# response from the iStore cloud used to flip every entity to unavailable; keeping
# the last good data rides out the 1-3 minute cloud blips.
MAX_STALE_POLLS = 10

# Default work mode when data is missing from coordinator
# 3 = Hybrid (heat pump + electric element) — safest fallback
DEFAULT_WORK_MODE = 3
