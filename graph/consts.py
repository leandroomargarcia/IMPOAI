MAX_ATTEMPTS = 3
ITEM_LIST_LIMIT = 20

# Placeholder until we scrape a live USD/ARS rate.
USD_ARS_RATE = 1535.0

# Decreto 1140/2024: 3 % until 2027-12-31, with USD caps. Not the AIA "RE" column.
ESTADISTICA_RATE = 3.0
ESTADISTICA_CAPS = (
    (10_000, 180.0),
    (100_000, 3_000.0),
    (1_000_000, 30_000.0),
    (float("inf"), 150_000.0),
)
MERCOSUR_ORIGINS = frozenset(
    {"argentina", "brasil", "brazil", "paraguay", "uruguay", "mercosur"}
)
