# Time periods in seconds
DAY = 86400
WEEK = 7 * DAY
YEAR = 52 * WEEK
MAX_TIME = 4 * YEAR

# Increase precision during slope and associated bias calculation
SLOPE_MULTIPLIER = 10 ** 18

# Token decimals
DECIMALS = 10 ** 18

# Multiplicative precision
PRECISION = 10 ** 18

# Precision for vote share calculation
VOTE_SHARE_MULTIPLIER = 10 ** 18

# PLY supply
MAX_SUPPLY = 100_000_000 * DECIMALS

# Initial weekly ply emission in number of tokens
INITIAL_EMISSION = 2_000_000 * DECIMALS

# Long term fixed trailing emission rate
TRAIL_EMISSION = 10_000 * DECIMALS

# The precision multiplier for drop percentages
DROP_GRANULARITY = 1_000_000

# Emission drop after the high initial rate for 4 weeks (period may change)
# This implies emission drops to 35% of the initial value
INITIAL_DROP = 35 * DROP_GRANULARITY  # Percentage with granularity

# Emission drop after every one year
YEARLY_DROP = 55 * DROP_GRANULARITY  # Percentage with granularity

# A factor to relax the reduction of emissions
EMISSION_FACTOR = 5
