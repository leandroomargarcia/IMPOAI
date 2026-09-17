from graph.state import GraphState


def join_branches(state: GraphState) -> dict:
    print(
        "JOIN ncm",
        state.get("ncm") or "(none)",
        "hab",
        bool(state.get("hab_info")),
        "price",
        state.get("precio_info") or "-",
        "duty",
        state.get("impuestos_estimados"),
    )
    return {}


def orchestrator(state: GraphState) -> dict:
    cif = state.get("cif")
    duty = state.get("impuestos_estimados")
    landed = None
    if cif is not None and duty is not None:
        landed = cif + duty
    report = "\n".join(
        [
            "IMPOAI — estimación de importación (no es un despacho AFIP / SIM / María).",
            f"Producto: {state.get('question') or '-'}",
            f"NCM: {state.get('ncm_info') or 'sin clasificar'}",
            f"CIF: {cif if cif is not None else '-'} USD",
            f"Origen: {state.get('origen') or '-'}",
            f"Provincia: {state.get('provincia') or '-'}",
            f"Inscripto: {'sí' if state.get('inscripto') else 'no' if state.get('inscripto') is False else '-'}",
            f"Derechos estimados: {duty if duty is not None else '-'} USD (DIE + estadística + medidas + IVA + percepciones + IIBB; no es un despacho).",
            f"CIF + derechos: {landed if landed is not None else '-'} USD",
            "Nota: ese subtotal es solo la liquidación fiscal. IMPOAI no calcula honorarios de despachante, depósito fiscal, gastos de terminal, flete interno, seguro local ni aranceles de habilitaciones; hay que sumarlos aparte (los cotiza el despachante, la terminal o el transportista).",
            f"Desglose: {state.get('costos_asociados') or '-'}",
            f"Precio de referencia venta Argentina: {state.get('precio_info') or 'sin datos'}",
            "Habilitaciones (trámites, no aranceles):",
            state.get("hab_info") or "(sin datos)",
        ]
    )
    print("REPORT ready")
    return {"reporte_final": report}
