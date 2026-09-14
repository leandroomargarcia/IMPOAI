from graph.state import GraphState

def calc_duty(state: GraphState) -> dict:
    aec = state.get("ncm_aec") or 0
    price = state.get("precio_ref") or 0
    duty = price * (aec / 100)
    currency = state.get("ncm_currency") or ""
    print("DUTY", duty, currency, f"(AEC {aec}%)")
    print("LANDED", price + duty, currency)
    return {"impuestos_estimados": duty}