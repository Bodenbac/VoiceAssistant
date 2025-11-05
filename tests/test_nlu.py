from voice_assistant.nlu.rule_based import SimpleRuleNLU


def test_nlu_rules_basic():
    nlu = SimpleRuleNLU()
    assert nlu.parse("what time is it").name == "get_time"
    assert nlu.parse("hello there").name == "greet"
    assert nlu.parse("please exit now").name == "exit"
    assert nlu.parse("something random").name == "fallback"

