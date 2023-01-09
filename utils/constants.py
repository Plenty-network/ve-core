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

# PLY total supply
MAX_SUPPLY = 1_000_000_000 * DECIMALS

# Initial weekly ply emission in number of tokens
INITIAL_EMISSION = 3_000_000 * DECIMALS

# The precision multiplier for drop percentages
DROP_GRANULARITY = 1_000_000

# Emission drop after the high initial rate for 4 weeks
# This implies emission drops to 66.666667% of the initial value (3M -> 2M)
INITIAL_DROP = int(66.666667 * DROP_GRANULARITY)  # Percentage with granularity

# Emission drop after every one year
YEARLY_DROP = int(70.710678 * DROP_GRANULARITY)  # Percentage with granularity

# A factor to relax the reduction of emissions
# 2 implies that reduction is relaxed by 50%
EMISSION_FACTOR = 2
