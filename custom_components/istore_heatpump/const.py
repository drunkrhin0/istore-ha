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

# Default work mode when data is missing from coordinator
# 3 = Hybrid (heat pump + electric element) — safest fallback
DEFAULT_WORK_MODE = 3
