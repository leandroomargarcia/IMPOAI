# TODO — IMPOAI

Hecho: catálogo NCM de 97 capítulos parseado del PDF (JSON, no RAG). POC de café/caballo/yerba sigue como regresión.

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
- [ ] Probar 3 productos fuera de los capítulos 1 y 9



## Lo que usa un despachante y todavía no tenemos

- [ ] **Ficha técnica** — pedir/armar composición, uso, presentación, si va armado. No clasificar solo con el nombre comercial
- [ ] **NESH** — cerrado: el libro de la OMA no es gratuito; no hay índice NESH en el repo
- [ ] **Criterios de clasificación AFIP/ARCA** — precedentes por posición NCM (RG + anexos; Arancel Integrado para consultar). Van después de `get_ncm`
- [ ] Si el producto puede ir a dos capítulos, comparar partidas con RGI 3 (más específica / carácter esencial / último número) en vez de casarse con el primer capítulo



## Liquidación al estilo despachante (simular, no reemplazar AFIP)

Hoy `calc_duty` hace `CIF × DIE%`. El usuario ingresa el **CIF** en la pregunta (no FOB + flete + seguro). Todavía no es un despacho. El objetivo es **simular la hoja del despachante** (presupuesto), no liquidar en el sistema aduanero.

### Modificar lo que ya está

- [x] Base = **CIF** ingresado por el usuario (el chat lo pedirá después)
- [ ] `impuestos_estimados` pasa a ser un **total de liquidación estimada**, no solo el AEC
- [x] Llenar `costos_asociados` con **desglose renglón a renglón** (CIF, DIE)
- [ ] Dejar explícito en el reporte que es una **estimación**, no una declaración SIM / María
- [ ] El nodo de impuestos sigue siendo **cuentas + tablas**, no un LLM ni un agente ReAct



### Derechos y tasas (sobre CIF)

- [x] Parsear dump Arancel Integrado (`docs/nomenclador_*.txt`) y usar DIE vigente como AEC en `get_ncm`
- [x] **AEC / derechos de importación** — aplicar la alícuota sobre CIF, no sobre FOB
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