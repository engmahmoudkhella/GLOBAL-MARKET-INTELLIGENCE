"""Bank of Israel adapter against the owner's recorded responses (2026-10-31, via browser)."""

import pathlib
from datetime import UTC, date, datetime
from decimal import Decimal as D

import httpx
import pytest

from app.providers.boi import (
    BankOfIsraelProvider,
    parse_latest_json,
    parse_sdmx_xml,
    series_code,
)
from app.providers.errors import CapabilityNotSupported, ProviderDataError

FIX = pathlib.Path(__file__).parents[1] / "fixtures" / "providers"
JSON = (FIX / "boi_exchange_rates.recorded-2026-10-31.json").read_text()
XML = (FIX / "boi_sdmx_rer_usd_ils.browser-copy-2026-10-31.xml").read_text()
NOW = datetime(2026, 10, 31, 10, 56, 27, tzinfo=UTC)


def provider(seen):
    def handler(req):
        seen.append(req)
        if req.url.host == "www.boi.org.il":
            return httpx.Response(200, text=JSON)
        if req.url.host == "edge.boi.org.il":
            return httpx.Response(200, text=XML)
        return httpx.Response(404)

    return BankOfIsraelProvider(
        transport=httpx.MockTransport(handler), sleep=lambda s: None, clock=lambda: NOW
    )


def test_series_code():
    assert series_code("usd") == "RER_USD_ILS"
    with pytest.raises(ValueError):
        series_code("US")


# --- Finding D: JSON numbers parsed as Decimal from raw text, divided by unit ---------------
def test_recorded_json_usd_exact_decimal_and_publication_time():
    r = parse_latest_json(JSON, "USD", NOW)
    assert str(r.rate) == "3.118"  # exact, no binary-float artefacts
    # Finding A: lastUpdate 10:21:03Z = 12:21 Israel time on Friday 30 Oct (IST, UTC+2)
    assert r.published_at == datetime(2026, 10, 30, 10, 21, 3, 773145, tzinfo=UTC)
    assert r.rate_date == date(2026, 10, 30)
    assert r.extra["current_change_pct"] == "0.12845215157353885677585100"  # a percentage
    assert r.extra["unit"] == "1" and r.extra["published_rate"] == "3.118"


@pytest.mark.parametrize(
    "key,per_unit,unit",
    [
        ("JPY", D("0.019822"), "100"),  # 1.9822 per 100 JPY
        ("LBP", D("0.00003"), "10"),  # 0.0003 per 10 LBP
        ("EUR", D("3.4932"), "1"),
    ],
)
def test_rates_divided_by_unit(key, per_unit, unit):
    r = parse_latest_json(JSON, key, NOW)
    assert r.rate == per_unit and r.extra["unit"] == unit


def test_negative_and_zero_change_accepted():
    assert parse_latest_json(JSON, "AUD", NOW).extra["current_change_pct"].startswith("-0.0091")
    assert parse_latest_json(JSON, "LBP", NOW).extra["current_change_pct"] == "0"


@pytest.mark.parametrize(
    "old,new",
    [
        ('"currentExchangeRate":3.118', '"currentExchangeRate":"3.118"'),  # string: contract change
        ('"currentExchangeRate":3.118', '"currentExchangeRate":-3.118'),
        ('"currentChange":0.12845215157353885677585100', '"currentChange":"0.13"'),
        (
            '"unit":1,"lastUpdate":"2026-10-30T10:21:03.7731459Z"},{"key":"GBP"',
            '"unit":0,"lastUpdate":"2026-10-30T10:21:03.7731459Z"},{"key":"GBP"',
        ),
    ],
)
def test_contract_violations_rejected(old, new):
    assert old in JSON
    with pytest.raises(ProviderDataError):
        parse_latest_json(JSON.replace(old, new, 1), "USD", NOW)


# --- Finding C/E: SDMX-ML 2.1 XML (structure from browser copy), attributes stored raw --------
def test_sdmx_xml_series_parsed_with_raw_attributes():
    rates = parse_sdmx_xml(XML, "USD", NOW)
    assert [(r.rate_date.isoformat(), str(r.rate)) for r in rates] == [
        ("2026-10-20", "3.106"),
        ("2026-10-21", "3.091"),
        ("2026-10-22", "3.107"),
        ("2026-10-23", "3.112"),
        ("2026-10-26", "3.078"),
        ("2026-10-28", "3.128"),
        ("2026-10-29", "3.114"),
        ("2026-10-30", "3.118"),
    ]
    first = rates[0].extra
    assert first["obs.RELEASE_STATUS"] == "YP"  # stored raw, not interpreted
    assert first["series.DATA_SOURCE"] == "BOI_MRKT" and first["series.CONF_STATUS"] == "F"
    assert "obs.OBS_VALUE" not in first


def test_sdmx_and_json_agree_on_2026_10_30():
    xml_rate = parse_sdmx_xml(XML, "USD", NOW)[-1]
    assert xml_rate.rate == parse_latest_json(JSON, "USD", NOW).rate == D("3.118")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda x: x.replace('SERIES_CODE="RER_USD_ILS"', 'SERIES_CODE="RER_EUR_ILS"'),
        lambda x: x.replace('UNIT_MULT="0"', 'UNIT_MULT="3"'),
        lambda x: x.replace('TIME_PERIOD="2026-10-20"', 'TIME_PERIOD="20/10/2026"'),
        lambda x: x.replace('OBS_VALUE="3.106"', 'OBS_VALUE="abc"'),
        lambda x: x.replace("StructureSpecificData", "GenericData"),
        lambda x: x.replace('UNIT_MULT="0" CONF_STATUS', 'UNIT_MULT="0"CONF_STATUS'),  # finding E
    ],
)
def test_bad_sdmx_rejected(mutate):
    with pytest.raises(ProviderDataError):
        parse_sdmx_xml(mutate(XML), "USD", NOW)


def test_xml_entity_expansion_refused():
    bomb = (
        '<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaaaa">'
        '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]>'
        "<StructureSpecificData>&b;</StructureSpecificData>"
    )
    with pytest.raises(ProviderDataError):
        parse_sdmx_xml(bomb, "USD", NOW)


# --- Finding C: verified hosts and paths ------------------------------------------------------
def test_adapter_uses_verified_hosts_and_no_format_param():
    seen = []
    p = provider(seen)
    assert p.get_latest_reference_rate("USD").rate == D("3.118")
    rates = p.get_reference_rates("USD", date(2026, 10, 20), date(2026, 10, 30))
    assert len(rates) == 8
    assert seen[0].url.host == "www.boi.org.il"
    assert seen[1].url.host == "edge.boi.org.il"
    assert seen[1].url.path == (
        "/FusionEdgeServer/sdmx/v2/data/dataflow/BOI.STATISTICS/EXR/1.0/RER_USD_ILS"
    )
    assert "format" not in seen[1].url.params
    assert seen[1].url.params["startperiod"] == "2026-10-20"


def test_boi_offers_no_market_quotes():
    with pytest.raises(CapabilityNotSupported):
        provider([]).get_latest_quote("USD")
