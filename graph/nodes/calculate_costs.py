from graph.state import GraphState


def calc_duty(state: GraphState) -> dict:
    fob = state.get("fob")
    if fob is None:
        print("no FOB from user, skip duty")
        return {"impuestos_estimados": 0}
    aec = state.get("ncm_aec") or 0
    duty = fob * (aec / 100)
    print("DUTY", duty, "USD", f"(AEC {aec}% of FOB {fob})")
    print("LANDED", fob + duty, "USD")
    return {"impuestos_estimados": duty}
