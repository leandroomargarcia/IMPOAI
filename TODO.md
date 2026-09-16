# TODO — IMPOAI

Hecho: catálogo NCM de 97 capítulos (JSON, no RAG). Office: NCM ∥ hab → join → precio → `calc_duty` → reporte. DIE del dump AIA; CIF y origen en la pregunta; medidas CNCE (antidumping ad valorem).

## Catálogo completo

- [x] Parsear los 97 capítulos del PDF (sacar `POC_CHAPTERS = {1, 9}`)
- [x] Resetear jerarquía cuando cambia la partida (caso `0903.00` sin `09.03`)
- [x] Aceptar AEC con flags `BK` / `BIT`
- [x] Saltar la tabla aeronáutica
- [x] Colgar notas de sección y de subpartida en el capítulo
- [x] Generar `ncm/data/catalog.json` (una sola vez, offline)
- [x] Auditar el JSON: 97 capítulos, ítems 8 dígitos, path con padre, AEC nulos
- [x] Regresión POC: `0901.11.10`, `0101.21.00`, `0903.00.10`
- [x] Spot-check capítulos 27, 39, 84
- [x] Si una partida tiene muchos ítems, listar primero subpartidas de 6 dígitos



## Grafo

- [x] Completar `GraphState` de la rama NCM (`ncm_chapter`, `ncm_notes`, `ncm_heading`, `ncm_item`, `ncm`, `ncm_aec`, `ncm_feedback`, `ncm_info`, …)
- [x] Partir `clasificar_ncm` en nodos: router → notas → partida → ítem → `get_ncm` → grade
- [x] Si `get_ncm` falla, no llamar al grader
- [x] Si se acaba el presupuesto sin groundear, `ncm_info` debe decir que no clasificó
- [x] Cablear el office: NCM ∥ hab → join → precio → AEC → orquestador
- [ ] Probar 3 productos fuera de los capítulos 1 y 9 (hubo corridas live de ibuprofeno / triciclo; no hay test fijo)



## Lo que usa un despachante y todavía no tenemos

- [ ] **Ficha técnica** — pedir/armar composición, uso, presentación, si va armado. No clasificar solo con el nombre comercial
- [x] **NESH** — cerrado: el libro de la OMA no es gratuito; no hay índice NESH en el repo
- [ ] **Criterios de clasificación AFIP/ARCA** — **prioridad muy baja (post-MVP)**. Cubren casos puntuales, no el flujo general. Si se hacen, van después de `get_ncm` como validación (no como clasificador). Hace falta dump de anexos de RG (Biblioteca ARCA); el nomenclador AIA no es esto.
- [ ] Si el producto puede ir a dos capítulos, comparar partidas con RGI 3 (más específica / carácter esencial / último número) en vez de casarse con el primer capítulo. **Después de la ficha técnica** (sin composición/uso el retry del grader alcanza). No es la próxima caja.



## Liquidación al estilo despachante (simular, no reemplazar AFIP)

Hoy `calc_duty` hace `CIF × DIE%` + tasa de estadística + medidas CNCE + **IVA** + **percepción IVA** + **percepción Ganancias** + **IIBB** (si hay provincia). Todavía no es un despacho.

### Modificar lo que ya está

- [x] Base = **CIF** ingresado por el usuario (el chat lo pedirá después)
- [x] `impuestos_estimados` pasa a ser un **total de liquidación estimada** (DIE + estadística + medidas + IVA + percepciones + IIBB)
- [x] Llenar `costos_asociados` con **desglose renglón a renglón** (CIF, DIE, estadística, medidas, IVA, percepciones, IIBB)
- [x] Dejar explícito en el reporte que es una **estimación**, no una declaración SIM / María
- [x] El nodo de impuestos sigue siendo **cuentas + tablas**, no un LLM ni un agente ReAct



### Derechos y tasas (sobre CIF)

- [x] Parsear dump Arancel Integrado (`docs/nomenclador_*.txt`) y usar DIE vigente como AEC en `get_ncm`
- [x] **AEC / derechos de importación** — aplicar la alícuota sobre CIF
- [x] Derechos **específicos**, antidumping o salvaguardias: lookup del xlsx CNCE por NCM; se suma ad valorem si hay origen; específico / FOB mínimo se informan, no se liquidan. Este dump no trae salvaguardias
- [x] Liquidar **específico** cuando el usuario da cantidad/unidad y el Excel tiene **una** tarifa (origen + unidad coinciden). Si hay varias (secas vs vapor) o es FOB mínimo, solo se avisa
- [x] **Tasa de estadística** — 3 % sobre CIF (Decreto 1140/2024), con topes en USD y 0 si el origen es Mercosur. No se usa la columna RE del nomenclador (no es esta tasa)
- [ ] Usar flags `BK` / `BIT` del catálogo en la liquidación (hoy se parsean y se guardan, `calc_duty` no los mira)



### IVA y percepciones AFIP

- [x] **IVA** 21 % default sobre CIF + DIE + estadística + medidas. Tabla 10,5 % por NCM: después. El usuario puede poner `IVA 10.5` (o `IVA exento`) en la pregunta
- [x] **IVA percepción (adicional)** — RG 2937/4461: 20 % si IVA 21 %, 10 % si IVA 10,5 %, misma base. 0 si IVA exento. Crédito para el inscripto
- [x] **Percepción Ganancias** — RG 2281: 11 % monotributista (**default**), 6 % si la pregunta dice `responsable inscripto`, 3 % `responsable inscripto CVDI`, 11 % uso particular, 0 con certificado de exclusión. Base: CIF + DIE + estadística + medidas (sin IVA, art. 6)
- [x] Guardar en el state si el usuario está **inscripto** (default no / monotributista; hay que aclarar `responsable inscripto`)



### IIBB

- [x] No usar un % nacional. Pedir **provincia** (o `IIBB 3.5` a mano) y aplicar alícuota general estimada de esa jurisdicción (tabla SIRPEI de presupuesto; no es el factor del CUIT)
- [x] Default 0 si el usuario no informa provincia



### Costos operativos (después de la liquidación aduanera)

- [ ] Honorarios de despachante (estimado; % de CIF o fijo)
- [ ] Depósito fiscal / terminal / flete interno / seguro local
- [ ] **Habilitaciones (SENASA/ANMAT, etc.)** — el nodo hab lista trámites, no montos. No costearlos como % del CIF. Opciones: el usuario carga el fee; tabla organismo → arancel; Tavily + extract (después)



### Precio local / FX (ya empezado)

- [ ] **Scrapear el tipo de cambio USD/ARS** (oficial o el que definamos para el negocio) en vez del fijo `USD_ARS_RATE` en `graph/consts.py`. Hoy el precio de venta en Argentina se extrae en pesos y se divide por esa constante para compararlo con el CIF en USD.
- [ ] Comparar **CIF + liquidación estimada** contra `precio_ref` (venta local en USD)
