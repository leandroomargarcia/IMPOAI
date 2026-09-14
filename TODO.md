# TODO — IMPOAI

Hecho: POC NCM con capítulos 1 y 9 (café, caballo, yerba) y pipeline secuencial capítulo → notas → partida → ítem → `get_ncm` → grade.

## Catálogo completo

- [ ] Parsear los 97 capítulos del PDF (sacar `POC_CHAPTERS = {1, 9}`)
- [ ] Resetear jerarquía cuando cambia la partida (caso `0903.00` sin `09.03`)
- [ ] Aceptar AEC con flags `BK` / `BIT`
- [ ] Saltar la tabla aeronáutica
- [ ] Colgar notas de sección y de subpartida en el capítulo
- [ ] Generar `ncm/data/catalog.json` (una sola vez, offline)
- [ ] Auditar el JSON: 97 capítulos, ítems 8 dígitos, path con padre, AEC nulos
- [ ] Regresión POC: `0901.11.10`, `0101.21.00`, `0903.00.10`
- [ ] Spot-check capítulos 27, 39, 84
- [ ] Si una partida tiene muchos ítems, listar primero subpartidas de 6 dígitos
- [ ] Dejar de chunkear el PDF en `ingestion.py`

## Grafo

- [ ] Completar `GraphState` de la rama NCM (`ncm_capitulo`, `ncm_notas`, `ncm_partida`, `ncm_item`, `ncm`, `ncm_aec`, `ncm_feedback`, …)
- [ ] Partir `clasificar_ncm` en nodos: router → notas → partida → ítem → `get_ncm` → grade
- [ ] Si `get_ncm` falla, no llamar al grader
- [ ] Si se acaba el presupuesto sin groundear, `ncm_info` debe decir que no clasificó
- [ ] Probar 3 productos fuera de los capítulos 1 y 9

## Lo que usa un despachante y todavía no tenemos

- [ ] **Ficha técnica** — pedir/armar composición, uso, presentación, si va armado. No clasificar solo con el nombre comercial
- [ ] **Notas explicativas (NESH)** — índice aparte de la NCM; inyectarlas por partida, no por similitud al PDF del AEC
- [ ] **Precedentes** — dictámenes AFIP/DGA, opiniones de clasificación, declaraciones parecidas
- [ ] Si el producto puede ir a dos capítulos, comparar partidas con RGI 3 (más específica / carácter esencial / último número) en vez de casarse con el primer capítulo

## Liquidación al estilo despachante (simular, no reemplazar AFIP)

Hoy `calc_duty` solo hace `FOB × AEC%`. Eso no es un despacho. El objetivo es **simular la hoja del despachante** (presupuesto), no liquidar en el sistema aduanero.

### Modificar lo que ya está

- [ ] Dejar de tratar el FOB como valor en aduana. Base = **CIF** = FOB + flete internacional + seguro (el usuario los carga; el chat los pedirá después)
- [ ] `impuestos_estimados` pasa a ser un **total de liquidación estimada**, no solo el AEC
- [ ] Llenar `costos_asociados` con **desglose renglón a renglón** (no un solo número)
- [ ] Dejar explícito en el reporte que es una **estimación**, no una declaración SIM / María
- [ ] El nodo de impuestos sigue siendo **cuentas + tablas**, no un LLM ni un agente ReAct

### Derechos y tasas (sobre CIF)

- [ ] **AEC / derechos de importación** — ya tenemos la alícuota del catálogo; aplicarla sobre CIF, no sobre FOB
- [ ] Derechos **específicos**, antidumping o salvaguardias si la posición los tiene (el POC no los parsea)
- [ ] **Tasa de estadística** — % sobre CIF, con exenciones, orígenes y topes (no un 3 % fijo eterno)
- [ ] Flags AEC `BK` / `BIT` y demás del PDF cuando el catálogo los traiga

### IVA y percepciones AFIP

- [ ] **IVA** 10,5 % o 21 % según NCM (tabla o default). Base: CIF + derechos + estadística
- [ ] **IVA percepción (adicional)** — RG vigente; depende de inscripción del importador
- [ ] **Percepción Ganancias** — RG vigente; no un % único para todos
- [ ] Guardar en el state si el usuario está **inscripto** (cambia percepciones)

### IIBB

- [ ] No usar un % nacional. Pedir **provincia** (o SIRPEI) y aplicar alícuota de esa jurisdicción
- [ ] Default 0 si el usuario no informa provincia

### Costos operativos (después de la liquidación aduanera)

- [ ] Honorarios de despachante (estimado; % de CIF o fijo)
- [ ] Depósito fiscal / terminal / flete interno / seguro local
- [ ] **Habilitaciones (SENASA/ANMAT, etc.)** — el nodo hab lista trámites, no montos. No costearlos como % del FOB. Opciones: el usuario carga el fee; tabla organismo → arancel; Tavily + extract (después)

### Precio local / FX (ya empezado)

- [ ] **Scrapear el tipo de cambio USD/ARS** (oficial o el que definamos para el negocio) en vez del fijo `USD_ARS_RATE` en `graph/consts.py`. Hoy el precio de venta en Argentina se extrae en pesos y se divide por esa constante para compararlo con el FOB en USD.
- [ ] Comparar **CIF + liquidación estimada** contra `precio_ref` (venta local en USD), no FOB solo
