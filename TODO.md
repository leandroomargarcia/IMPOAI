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
- [ ] **Criterios de clasificación AFIP/ARCA** — precedentes por posición NCM (RG + anexos; Biblioteca ARCA). Van después de `get_ncm`. Hace falta el dump (PDF/JSON); el nomenclador AIA no es esto
- [ ] Si el producto puede ir a dos capítulos, comparar partidas con RGI 3 (más específica / carácter esencial / último número) en vez de casarse con el primer capítulo



## Liquidación al estilo despachante (simular, no reemplazar AFIP)

Hoy `calc_duty` hace `CIF × DIE%` + tasa de estadística (3 % con tope, 0 si origen Mercosur) + antidumping **ad valorem** si hay origen y el xlsx CNCE matchea. Específico / FOB mínimo se informan, no se liquidan. Todavía no es un despacho.

### Modificar lo que ya está

- [x] Base = **CIF** ingresado por el usuario (el chat lo pedirá después)
- [ ] `impuestos_estimados` pasa a ser un **total de liquidación estimada** (hoy: DIE + estadística + AD ad valorem; faltan IVA, percepciones, IIBB)
- [x] Llenar `costos_asociados` con **desglose renglón a renglón** (CIF, DIE, estadística, medidas)
- [x] Dejar explícito en el reporte que es una **estimación**, no una declaración SIM / María
- [x] El nodo de impuestos sigue siendo **cuentas + tablas**, no un LLM ni un agente ReAct



### Derechos y tasas (sobre CIF)

- [x] Parsear dump Arancel Integrado (`docs/nomenclador_*.txt`) y usar DIE vigente como AEC en `get_ncm`
- [x] **AEC / derechos de importación** — aplicar la alícuota sobre CIF
- [x] Derechos **específicos**, antidumping o salvaguardias: lookup del xlsx CNCE por NCM; se suma ad valorem si hay origen; específico / FOB mínimo se informan, no se liquidan. Este dump no trae salvaguardias
- [ ] Liquidar **específico** cuando el usuario dé cantidad/unidad (hoy solo se avisa)
- [x] **Tasa de estadística** — 3 % sobre CIF (Decreto 1140/2024), con topes en USD y 0 si el origen es Mercosur. No se usa la columna RE del nomenclador (no es esta tasa)
- [ ] Usar flags `BK` / `BIT` del catálogo en la liquidación (hoy se parsean y se guardan, `calc_duty` no los mira)



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
- [ ] **Habilitaciones (SENASA/ANMAT, etc.)** — el nodo hab lista trámites, no montos. No costearlos como % del CIF. Opciones: el usuario carga el fee; tabla organismo → arancel; Tavily + extract (después)



### Precio local / FX (ya empezado)

- [ ] **Scrapear el tipo de cambio USD/ARS** (oficial o el que definamos para el negocio) en vez del fijo `USD_ARS_RATE` en `graph/consts.py`. Hoy el precio de venta en Argentina se extrae en pesos y se divide por esa constante para compararlo con el CIF en USD.
- [ ] Comparar **CIF + liquidación estimada** contra `precio_ref` (venta local en USD)
