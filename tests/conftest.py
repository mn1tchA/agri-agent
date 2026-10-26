"""
Global pytest fixtures and test configuration.
"""

from unittest.mock import MagicMock

import httpx
import pytest


@pytest.fixture(autouse=True)
def mock_open_meteo(monkeypatch):
    """
    Mock external calls to api.open-meteo.com to ensure deterministic, fast,
    and offline test execution across all environments and CI runners.
    """
    orig_get = httpx.AsyncClient.get

    async def mocked_get(self, url, *args, **kwargs):
        url_str = str(url)
        if "api.open-meteo.com" in url_str:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()

            data = {
                "current": {
                    "temperature_2m": 25.0,
                    "relative_humidity_2m": 50.0,
                    "soil_moisture_0_to_1cm": 0.18,
                    "soil_moisture_3_to_9cm": 0.18,
                },
                "daily": {
                    "precipitation_sum": [0.0, 0.0, 0.0],
                    "et0_fao_evapotranspiration": [3.5, 3.5, 3.5],
                },
            }
            mock_resp.json = MagicMock(return_value=data)
            return mock_resp
        return await orig_get(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "get", mocked_get)
