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
