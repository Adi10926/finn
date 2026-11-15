"""Core logic tests: classification, materiality, results maths, alerts, research. Offline."""
import os
os.environ["FINN_LIVE"] = "0"
os.environ["FINN_AS_OF"] = "2026-11-15"

from finn.alerts import eod_alerts
from finn.engine import company, parse_ask
from finn.research import dossier
from finn.results import headline
from finn.taxonomy import amount_cr, classify, person, score


def test_classify_precedence():
    assert classify("Earnings Call Transcript", "Transcript of discussion on unaudited results") == "earnings_call"
    assert classify("Newspaper Publication", "Copy of newspaper publication of unaudited results") == "results_ad"
    # a postal-ballot subject that actually approves a CEO is a management change
    assert classify("Shareholder Meeting / Postal Ballot-Outcome of Postal Ballot",
                    "Shareholders approved Anup Bagchi as Director and MD & CEO") == "management_change"
    assert classify("Bagging/receiving of order(s) or contract(s)", "won a metro order") == "order_win"
    assert classify("Intimation of Repayment of Commercial Paper (CP)", "") == "unclassified"
    assert classify("Monitoring Agency Report", "no deviation in QIP proceeds") == "fund_use"


def test_person_and_amount():
    assert person("HDFC Bank reappointed V. Srinivasa Rangan as Executive Director") == "V. Srinivasa Rangan"
    assert person("Mr. Sanjay D'Souza superannuated") == "Sanjay D'Souza"
    assert amount_cr("floor price of Rs 992.25; warrants at Rs 1,010 each (Rs 5,800 Cr)") == 5800
    assert amount_cr("floor price of Rs 992.25") is None   # per-share price is not a deal size


def test_materiality_is_relative():
    lt = company("LT")
    s = score({"title": "Bagging of order", "desc": "L&T won significant orders"}, lt, [])
    assert s["facts"]["pct_ttm_rev"] < 1 and s["tier"] != "act"
    hd = company("HDFCBANK")
    re_ = score({"title": "Change in Directorate", "desc": "reappointed V. Srinivasa Rangan as Executive Director"}, hd, [])
    ceo = score({"title": "Outcome of Postal Ballot", "desc": "Shareholders approved Anup Bagchi as Director and MD & CEO"}, hd, [])
    assert ceo["score"] > re_["score"] and ceo["tier"] == "act"


def test_results_headline_dixon():
    h = headline(company("DIXON"))
    m = {x["key"]: x for x in h["metrics"]}
    assert h["quarter"] == "Sep 2026" and h["yago_quarter"] == "Sep 2025"
    assert m["sales"]["cur"] == 21794 and round(m["pat"]["yoy"]) == -45
    assert any(f["kind"] == "divergence" for f in h["flags"])


def test_bank_has_no_ebitda():
    h = headline(company("HDFCBANK"))
    assert next(x for x in h["metrics"] if x["key"] == "op").get("na")


def test_eod_alerts_threshold():
    s = [{"date": f"d{i}", "close": 100, "volume": 100} for i in range(25)]
    s.append({"date": "spike", "close": 106, "volume": 300})
    a = eod_alerts(s, 2.0, 20, 4.0)
    assert a and {h["rule"] for h in a[-1]["hits"]} == {"volume", "price"}
    assert not eod_alerts(s, 3.5, 20, 7.0)


def test_research_promise_checks():
    d = dossier(company("DIXON"))
    verdicts = {c["verdict"] for c in d["guidance"]["checks"]}
    assert "ahead" in verdicts and any("falling" in v for v in verdicts)
    assert d["cash"]["cum"] > 1


def test_parse_ask():
    p = parse_ask("what did DIXON promise vs deliver?", ["DIXON", "TCS"])
    assert p == {"symbol": "DIXON", "intent": "guidance"}
