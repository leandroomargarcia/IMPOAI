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

# Import VAT default. 10.5 % by NCM is a later table; the question may override.
IVA_RATE = 21.0
IVA_REDUCED_RATE = 10.5

# RG 2937 / 4461: percepción IVA on the same art. 25 base as IVA.
IVA_PERC_GENERAL = 20.0
IVA_PERC_REDUCED = 10.0

# RG 2281: percepción Ganancias. Default = monotributista (11%). Inscripto is 6%.
GANANCIAS_PERC_INSCRIPTO = 6.0
GANANCIAS_PERC_CVDI = 3.0
GANANCIAS_PERC_PARTICULAR = 11.0
