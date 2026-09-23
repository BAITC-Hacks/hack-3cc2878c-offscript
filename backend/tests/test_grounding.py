from app.agent.briefing import is_grounded, template


def test_grounding_rejects_unknown_number():
    facts = {"mean": 0.44, "energy": 55.2}
    assert is_grounded("Output is 44% and energy is 55.2 MWh.", facts)
    assert not is_grounded("Output is 99%.", facts)


def test_template_is_grounded():
    forecast = {"summary": {"dayahead_mean_p50": 0.44, "energy_p50_mwh": 55.2, "mean_band": 0.38}}
    briefing = template(forecast, []).en
    assert briefing.grounded
    assert briefing.generated_by == "template"
