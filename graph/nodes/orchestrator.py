from graph.state import GraphState


def join_branches(state: GraphState) -> dict:
    print("JOIN ncm", state.get("ncm") or "(none)", "hab", bool(state.get("hab_info")))
    return {}


def orchestrator(state: GraphState) -> dict:
    fob = state.get("fob")
    duty = state.get("impuestos_estimados")
    landed = None
    if fob is not None and duty is not None:
        landed = fob + duty
    report = "\n".join(
        [
            "IMPOAI — estimación de importación (no es un despacho AFIP / SIM / María).",
            f"Producto: {state.get('question') or '-'}",
            f"NCM: {state.get('ncm_info') or 'sin clasificar'}",
            f"FOB: {fob if fob is not None else '-'} USD",
            f"Derecho AEC estimado: {duty if duty is not None else '-'} USD (FOB × AEC%; no es CIF ni liquidación completa).",
            f"FOB + AEC: {landed if landed is not None else '-'} USD",
            f"Precio de referencia venta Argentina: {state.get('precio_ref') if state.get('precio_ref') is not None else '-'} USD",
            "Habilitaciones (trámites, no aranceles):",
            state.get("hab_info") or "(sin datos)",
        ]
    )
    print("REPORT ready")
    return {"reporte_final": report}
