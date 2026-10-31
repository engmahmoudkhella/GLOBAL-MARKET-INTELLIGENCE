import pathlib
from datetime import UTC, date, datetime
from decimal import Decimal as D

import httpx
import pytest

from app.providers.boi import BankOfIsraelProvider, parse_sdmx_csv, series_code
from app.providers.errors import CapabilityNotSupported, ProviderDataError

FIX = pathlib.Path(__file__).parents[1] / "fixtures" / "providers"
NOW = datetime(2026, 11, 4, 14, 0, tzinfo=UTC)


def provider(responses, seen=None):
    def handler(req):
        if seen is not None:
            seen.append(req)
        for (host, path), body in responses.items():
            if req.url.host == host and req.url.path.startswith(path):
                return httpx.Response(200, text=body)
        return httpx.Response(404)

    return BankOfIsraelProvider(
        transport=httpx.MockTransport(handler), sleep=lambda s: None, clock=lambda: NOW
    )


def test_series_code():
    assert series_code("usd") == "RER_USD_ILS"
    with pytest.raises(ValueError):
        series_code("US")


def test_latest_reference_rate_normalizes_unit_and_israel_date():
    p = provider(
        {
            ("boi.org.il", "/PublicApi/GetExchangeRates"): (
                FIX / "boi_exchange_rates.json"
            ).read_text()
        }
    )
    r = p.get_latest_reference_rate("USD")
    assert r.rate == D("3.712") and r.rate_date == date(2026, 11, 4)
    assert r.published_at == datetime(2026, 11, 4, 13, 25, 1, 456789, tzinfo=UTC)
    jpy = p.get_latest_reference_rate("JPY")
    assert jpy.rate == D("0.02451")  # per 1 unit (published per 100)


def test_latest_reference_missing_currency_raises():
    p = provider({("boi.org.il", "/PublicApi"): '{"exchangeRates": []}'})
    with pytest.raises(ProviderDataError):
        p.get_latest_reference_rate("USD")


def test_history_sdmx_csv_skips_blank_never_fills():
    seen = []
    p = provider(
        {("edge.boi.gov.il", "/FusionEdgeServer"): (FIX / "boi_rer_usd_ils.csv").read_text()}, seen
    )
    rates = p.get_reference_rates("USD", date(2026, 11, 1), date(2026, 11, 4))
    assert [(r.rate_date, r.rate) for r in rates] == [
        (date(2026, 11, 2), D("3.725")),
        (date(2026, 11, 3), D("3.719")),
    ]
    assert seen[0].url.path.endswith("/RER_USD_ILS")
    assert seen[0].url.params["startperiod"] == "2026-11-01"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "DATE,VALUE\n2026-11-02,3.7\n",  # wrong columns
        "SERIES_CODE,TIME_PERIOD,OBS_VALUE\nRER_EUR_ILS,2026-11-02,4.0\n",  # wrong series
        "TIME_PERIOD,OBS_VALUE\n02/11/2026,3.7\n",  # bad date
        "TIME_PERIOD,OBS_VALUE\n2026-11-02,abc\n",  # bad number
        "TIME_PERIOD,OBS_VALUE\n2026-11-02,3.7\n2026-11-02,3.8\n",  # conflicting duplicate
    ],
)
def test_bad_sdmx_csv_raises(text):
    with pytest.raises(ProviderDataError):
        parse_sdmx_csv(text, "USD", NOW)


def test_boi_offers_no_market_quotes():
    with pytest.raises(CapabilityNotSupported):
        provider({}).get_latest_quote("USD")
