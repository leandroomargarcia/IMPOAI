MAX_ATTEMPTS = 3
ITEM_LIST_LIMIT = 20

# Fallback if the BCRA A 3500 feed is down. Live quote: graph.nodes.search_price.fetch_usd_ars_rate.
USD_ARS_RATE = 1535.0
BCRA_USD_URL = "https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones/USD"

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

# SIRPEI: perception is CUIT-specific. These are general-rate estimates for budgeting.
# Keys are fold(name) with spaces stripped. Santa Fe 2.5 % is RG API 2/2013 (imports).
IIBB_ALIASES = {
    "caba": "CABA",
    "capitalfederal": "CABA",
    "ciudadautonoma": "CABA",
    "ciudaddebuenosaires": "CABA",
    "buenosaires": "Buenos Aires",
    "pba": "Buenos Aires",
    "bsas": "Buenos Aires",
    "bsaires": "Buenos Aires",
    "catamarca": "Catamarca",
    "chaco": "Chaco",
    "chubut": "Chubut",
    "cordoba": "Córdoba",
    "corrientes": "Corrientes",
    "entrerios": "Entre Ríos",
    "formosa": "Formosa",
    "jujuy": "Jujuy",
    "lapampa": "La Pampa",
    "larioja": "La Rioja",
    "mendoza": "Mendoza",
    "misiones": "Misiones",
    "neuquen": "Neuquén",
    "rionegro": "Río Negro",
    "salta": "Salta",
    "sanjuan": "San Juan",
    "sanluis": "San Luis",
    "santacruz": "Santa Cruz",
    "santafe": "Santa Fe",
    "santiagodelestero": "Santiago del Estero",
    "santiago": "Santiago del Estero",
    "tierradelfuego": "Tierra del Fuego",
    "tdf": "Tierra del Fuego",
    "tucuman": "Tucumán",
}
IIBB_RATES = {
    "CABA": 3.0,
    "Buenos Aires": 3.5,
    "Catamarca": 3.5,
    "Chaco": 3.5,
    "Chubut": 3.5,
    "Córdoba": 3.5,
    "Corrientes": 3.5,
    "Entre Ríos": 3.5,
    "Formosa": 3.0,
    "Jujuy": 3.5,
    "La Pampa": 3.5,
    "La Rioja": 3.5,
    "Mendoza": 3.0,
    "Misiones": 3.5,
    "Neuquén": 4.0,
    "Río Negro": 3.5,
    "Salta": 3.5,
    "San Juan": 3.0,
    "San Luis": 3.5,
    "Santa Cruz": 3.0,
    "Santa Fe": 2.5,
    "Santiago del Estero": 3.5,
    "Tierra del Fuego": 3.0,
    "Tucumán": 3.5,
}
