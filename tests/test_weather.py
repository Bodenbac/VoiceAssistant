from voice_assistant.apis.weather import RestWeatherClient

def test_weather():
    weather_client = RestWeatherClient()
    weather = weather_client.current("New York")
    assert type(weather) == dict
    assert weather["place"] == "New York"
    assert type(weather["forecast"]) == list
    assert type(weather["forecast"][0]) == dict
    assert type(weather["forecast"][0]["temperature"]) == dict
    assert type(weather["forecast"][0]["weather"]) == str
