"""lex.uz sync: page parsing (HTML fixtures shaped like real lex.uz pages), the polite client (spacing, Retry-After,
budget), incremental runs (added -> 304 unchanged -> updated -> suspect), search resolution of decrees, scheduling,
and the index builder preferring synced texts over the snapshot."""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from lex_agent.ingestion.lex_sync import (
    BUNDLES,
    CATALOG_OUT,
    STATE_FILE,
    CatalogEntry,
    LexSync,
    PoliteClient,
    SyncBudgetExhausted,
    build_records,
    load_sync_catalog,
    parse_act_html,
    parse_search_results,
    records_digest,
    sync_status,
)

FIX = Path(__file__).parent / "fixtures" / "lexuz"
LABOUR = CatalogEntry(slug="6257288", key="6257288", kind="code", priority=1, short_uz="Меҳнат кодекси",
                      short_ru="Трудовой кодекс", ru_id="6257291", branches=["labor"])


def _html(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


class FakeTime:
    """Deterministic clock + sleep for the rate limiter."""

    def __init__(self) -> None:
        self.t = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.t

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(round(seconds, 3))
        self.t += seconds


class FakeLexUz:
    """In-memory lex.uz: pages by path, ETags, conditional requests and scripted failures."""

    def __init__(self, pages: dict[str, str], etags: dict[str, str] | None = None) -> None:
        self.pages = dict(pages)
        self.etags = dict(etags or {})
        self.failures: dict[str, list[httpx.Response]] = {}
        self.seen: list[tuple[str, dict[str, str]]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.raw_path.decode()
        self.seen.append((path, dict(request.headers)))
        if self.failures.get(path):
            return self.failures[path].pop(0)
        if path not in self.pages:
            return httpx.Response(404, text="not found")
        etag = self.etags.get(path)
        if etag and request.headers.get("if-none-match") == etag:
            return httpx.Response(304)
        headers = {"ETag": etag} if etag else {}
        return httpx.Response(200, text=self.pages[path], headers=headers)


def _client(server: FakeLexUz, clock: FakeTime | None = None, **kw: Any) -> PoliteClient:
    clock = clock or FakeTime()
    return PoliteClient(transport=httpx.MockTransport(server.handler), sleep=clock.sleep, clock=clock.clock, **kw)


# ------------------------------------------------------------------------------------------------ parsing


def test_parse_act_page_structure() -> None:
    act = parse_act_html(_html("labour_uz.html"), lang="uz")
    assert act.title == "Ўзбекистон Республикасининг Меҳнат кодекси"
    assert act.number == "ЎРҚ-798" and act.adopted == "2022-10-28"
    # the language switcher (not the cross-reference to the Civil Code) gives the other editions
    assert act.editions == {"uz": "6257288", "ru": "6257291"}
    ids = [(a.article_id, a.display) for a in act.articles]
    assert ids == [("1", "1-модда"), ("217", "217-модда"), ("217.1", "217¹-модда"), ("218", "218-модда")]
    art217 = act.articles[1]
    assert art217.chapter == "26-боб. Меҳнат таътиллари" and art217.section == "I БЎЛИМ. УМУМИЙ ҚОИДАЛАР"
    assert art217.lines == ["Ҳар йилги асосий энг кам меҳнат таътилининг давомийлиги йигирма бир календарь кунни ташкил этади."]
    assert art217.notes and "ЎРҚ-1030" in art217.notes[0]
    joined = "\n".join(line for a in act.articles for line in a.lines)
    assert "LexUZ шарҳи" not in joined and "Классификатор" not in joined and "ҳавола олиш" not in joined
    assert "Иш стажи — Кунлар" in act.articles[2].lines  # table rows as text


def test_records_use_the_bundle_format_and_drop_the_signature() -> None:
    act = parse_act_html(_html("labour_uz.html"), lang="uz")
    recs = build_records(act, key="6257288", lex_id="6257288", entry=LABOUR, snapshot="2026-11-21")
    by_id = {r["article_id"]: r for r in recs}
    assert set(by_id) == {"1", "217", "217.1", "218", "annex"}
    assert by_id["218"]["text"].startswith("Ўн саккиз ёшга") and "МИРЗИЁЕВ" not in by_id["218"]["text"]
    assert by_id["annex"]["article_display"] == "Илова" and "намунавий шакли" in by_id["annex"]["text"]
    assert by_id["217"]["notes"][0]["act"] == "ЎРҚ-1030" and by_id["217"]["notes"][0]["published"] == "13.02.2025"
    rec = by_id["217"]
    assert rec["source"] == "lex_uz_sync" and rec["lang"] == "uz_cyrl" and rec["doc_type"] == "code"
    assert rec["short_title"] == "Меҳнат кодекси" and rec["doc_number"] == "ЎРҚ-798"
    # the same keys as a LawCodex record, so the index builder needs no special path
    lawcodex_keys = {"source", "lang", "doc_key", "lex_doc_id", "doc_title", "short_title", "doc_number", "doc_type",
                     "adopted", "snapshot", "article_id", "article_display", "article_title", "section", "chapter",
                     "text"}
    assert lawcodex_keys <= set(rec)
    # digest ignores snapshot labels but not text
    again = build_records(act, key="6257288", lex_id="6257288", entry=LABOUR, snapshot="2030-01-01")
    assert records_digest(recs) == records_digest(again)
    from lex_agent.ingestion.open_corpora import corpus_record_to_chunks

    chunk = corpus_record_to_chunks(rec)[0]
    assert chunk.canonical_id == "6257288" and chunk.extra["article_id"] == "217"


def test_russian_page_decree_page_and_card_only_page() -> None:
    ru = parse_act_html(_html("labour_ru.html"), lang="ru")
    assert [(a.article_id, a.display) for a in ru.articles] == [("217", "Статья 217"), ("217.1", "Статья 217¹")]
    assert ru.number == "ЗРУ-798" and ru.adopted == "2022-10-28"
    decree = parse_act_html(_html("decree_ru.html"), lang="ru")
    # the signature date wins over dates mentioned in the text ("с 1 сентября 2026 года")
    assert decree.number == "УП-115" and decree.adopted == "2026-06-23" and decree.has_text
    entry = CatalogEntry(slug="minimum-wage-2026", key=None, kind="presidential_decree", priority=2)
    recs = build_records(decree, key="7900115", lex_id="7900115", entry=entry, snapshot="2026-11-21")
    assert len(recs) == 1 and recs[0]["article_id"] is None and "440 000" in recs[0]["text"]
    assert recs[0]["doc_type"] == "presidential_decree"
    assert parse_act_html(_html("card_only.html"), lang="uz").has_text is False


def test_search_results_rows() -> None:
    rows = parse_search_results(_html("search_ru.html"))
    assert [r[0] for r in rows] == ["5555001", "7900115", "7553324"]
    assert rows[1][1] == "О повышении размеров заработной платы, пенсий, стипендий и пособий"
    assert "УП-115" in rows[1][2]


def test_catalog_has_about_200_acts_with_verified_ids() -> None:
    catalog = load_sync_catalog()
    assert 180 <= len(catalog) <= 220
    keys = [e.key for e in catalog if e.key]
    assert len(keys) == len(set(keys))
    assert {"6257288", "104720", "97664", "4704", "3336169", "112314", "6764454"} <= set(keys)
    assert all(e.find for e in catalog if not e.key)  # unverified entries are resolved by search, then checked
    assert {e.priority for e in catalog} == {1, 2, 3}


# ------------------------------------------------------------------------------------------------ polite client


@pytest.mark.asyncio
async def test_client_spacing_retry_after_and_budget() -> None:
    server = FakeLexUz({"/docs/1": "ok", "/docs/2": "ok"})
    server.failures["/docs/1"] = [httpx.Response(429, headers={"Retry-After": "7"})]
    clock = FakeTime()
    client = _client(server, clock, rps=0.5, max_requests=3)
    first = await client.get("/docs/1")
    assert first.status == 200 and client.requests == 2
    assert 7.0 in clock.sleeps  # Retry-After honoured
    await client.get("/docs/2")
    assert clock.sleeps.count(2.0) >= 1  # 0.5 rps = 2 s between requests
    with pytest.raises(SyncBudgetExhausted):
        await client.get("/docs/2")
    assert client.requests == 3
    ua = server.seen[0][1]["user-agent"]
    assert "HaqliLexAgent" in ua and "github.com" in ua
    await client.close()


# ------------------------------------------------------------------------------------------------ incremental sync


def _bundle(corpus: Path, lang: str) -> list[dict[str, Any]]:
    with gzip.open(corpus / BUNDLES[lang], "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


@pytest.mark.asyncio
async def test_sync_added_unchanged_updated_and_suspect(tmp_path: Path) -> None:
    server = FakeLexUz({"/docs/6257288": _html("labour_uz.html"), "/ru/docs/6257291": _html("labour_ru.html")},
                       etags={"/docs/6257288": '"v1"', "/ru/docs/6257291": '"r1"'})
    sync = LexSync(tmp_path, catalog=[LABOUR], client=_client(server, max_requests=50))

    first = await sync.run()
    assert (first.added, first.updated, first.failed) == (2, 0, 0)
    uz = _bundle(tmp_path, "uz")
    assert {r["article_id"] for r in uz} == {"1", "217", "217.1", "218", "annex"}
    assert {r["lex_doc_id"] for r in _bundle(tmp_path, "ru")} == {"6257291"}
    cat = json.loads((tmp_path / CATALOG_OUT).read_text(encoding="utf-8"))["documents"][0]
    assert cat["doc_key"] == "6257288" and cat["ru_id"] == "6257291" and cat["number_uz"] == "ЎРҚ-798"

    # second run: lex.uz answers 304 to the conditional request -> nothing is parsed or rewritten
    mtime = (tmp_path / BUNDLES["uz"]).stat().st_mtime_ns
    second = await sync.run(only=["6257288"])
    assert (second.unchanged, second.added, second.updated) == (2, 0, 0)
    assert server.seen[-1][1].get("if-none-match") == '"r1"'
    assert (tmp_path / BUNDLES["uz"]).stat().st_mtime_ns == mtime

    # the act is amended on lex.uz
    server.pages["/docs/6257288"] = _html("labour_uz.html").replace("йигирма бир календарь", "йигирма тўрт календарь")
    server.etags["/docs/6257288"] = '"v2"'
    third = await sync.run(only=["6257288"])
    assert (third.updated, third.unchanged) == (1, 1)
    assert third.changes[0]["kind"] == "updated" and third.changes[0]["lang"] == "uz"
    text217 = next(r["text"] for r in _bundle(tmp_path, "uz") if r["article_id"] == "217")
    assert "йигирма тўрт" in text217

    # a broken page (far fewer articles than stored) is not trusted: the stored text stays
    sync.state.edition("6257288", "uz")["articles"] = 40
    server.pages["/docs/6257288"] = _html("labour_uz.html").split('<div class="CLAUSE_DEFAULT">217-модда')[0] + "</div></body></html>"
    server.etags["/docs/6257288"] = '"v3"'
    fourth = await sync.run(only=["6257288"])
    assert fourth.suspect == 1 and any("suspect" in e for e in fourth.errors)
    assert "йигирма тўрт" in next(r["text"] for r in _bundle(tmp_path, "uz") if r["article_id"] == "217")
    state = json.loads((tmp_path / STATE_FILE).read_text(encoding="utf-8"))
    assert state["acts"]["6257288"]["editions"]["uz"]["status"] == "suspect"
    assert len(state["runs"]) == 4
    await sync.close()


@pytest.mark.asyncio
async def test_check_only_writes_no_text_and_failures_keep_old_data(tmp_path: Path) -> None:
    server = FakeLexUz({"/docs/6257288": _html("card_only.html")})
    sync = LexSync(tmp_path, catalog=[LABOUR], client=_client(server))
    report = await sync.run(check_only=True)
    assert report.failed == 2  # uz: no act text on the page; ru: 404
    assert not (tmp_path / BUNDLES["uz"]).exists() and not (tmp_path / CATALOG_OUT).exists()
    assert any("no act text" in e for e in report.errors)
    await sync.close()


@pytest.mark.asyncio
async def test_budget_defers_the_rest_to_the_next_run(tmp_path: Path) -> None:
    pages = {"/docs/6257288": _html("labour_uz.html"), "/ru/docs/6257291": _html("labour_ru.html")}
    other = CatalogEntry(slug="104720", key="104720", kind="code", priority=1, ru_id="104723")
    sync = LexSync(tmp_path, catalog=[LABOUR, other], client=_client(FakeLexUz(pages), max_requests=2))
    report = await sync.run()
    assert report.requests == 2 and report.deferred == 1
    assert sync_status(tmp_path, catalog=[LABOUR, other])["due"] == 1  # the deferred act is still due
    await sync.close()


@pytest.mark.asyncio
async def test_decree_resolved_by_search_verified_and_linked_to_uzbek_edition(tmp_path: Path) -> None:
    entry = CatalogEntry(slug="minimum-wage-2026", key=None, kind="presidential_decree", priority=2,
                         short_uz="ПФ-115", short_ru="УП-115",
                         find={"query_ru": "о повышении размеров заработной платы", "number": "115",
                               "terms": ["заработной платы", "пенси"]})
    server = FakeLexUz({
        "/ru/search/all?searchtitle=%D0%BE+%D0%BF%D0%BE%D0%B2%D1%8B%D1%88%D0%B5%D0%BD%D0%B8%D0%B8+%D1%80%D0%B0%D0%B7"
        "%D0%BC%D0%B5%D1%80%D0%BE%D0%B2+%D0%B7%D0%B0%D1%80%D0%B0%D0%B1%D0%BE%D1%82%D0%BD%D0%BE%D0%B9+%D0%BF%D0%BB%D0%B0"
        "%D1%82%D1%8B": _html("search_ru.html"),
        "/ru/docs/7900115": _html("decree_ru.html"),
        "/docs/7900113": _html("decree_uz.html"),
    })
    sync = LexSync(tmp_path, catalog=[entry], client=_client(server))
    report = await sync.run()
    assert report.unresolved == 0 and report.added == 2, report.errors
    st = sync.state.act("minimum-wage-2026")
    assert st["ru_id"] == "7900115" and st["uz_id"] == "7900113" and st["key"] == "7900115"
    ru = _bundle(tmp_path, "ru")
    assert ru[0]["doc_key"] == "7900115" and ru[0]["doc_number"] == "УП-115"
    assert _bundle(tmp_path, "uz")[0]["lex_doc_id"] == "7900113"
    # the next run reuses the resolved ids (no search request)
    searches = sum(1 for p, _h in server.seen if "/search" in p)
    await sync.run(only=["minimum-wage-2026"])
    assert sum(1 for p, _h in server.seen if "/search" in p) == searches
    await sync.close()


@pytest.mark.asyncio
async def test_unmatched_search_results_are_not_stored(tmp_path: Path) -> None:
    entry = CatalogEntry(slug="x", key=None, kind="cabinet_resolution", priority=2,
                         find={"query_ru": "правила дорожного движения", "terms": ["дорожного движения"]})
    server = FakeLexUz({})
    sync = LexSync(tmp_path, catalog=[entry], client=_client(server))
    report = await sync.run()
    assert report.unresolved == 1 and report.added == 0
    assert sync.state.act("x")["status"] == "unresolved"
    await sync.close()


def test_scheduling_by_priority_age(tmp_path: Path) -> None:
    now = datetime(2026, 11, 21, 3, 0, tzinfo=timezone.utc)
    p1 = CatalogEntry(slug="a", key="1", kind="code", priority=1)
    p3 = CatalogEntry(slug="b", key="2", kind="law", priority=3)
    sync = LexSync(tmp_path, catalog=[p1, p3], client=PoliteClient(), now=lambda: now)
    sync.state.edition("a", "uz")["checked_at"] = (now - timedelta(days=3)).isoformat()
    sync.state.edition("b", "uz")["checked_at"] = (now - timedelta(days=3)).isoformat()
    assert [e.slug for e in sync.due()] == ["a"]  # priority 1 every 2 days, priority 3 every 14
    assert {e.slug for e in sync.due(force=True)} == {"a", "b"}
    assert [e.slug for e in sync.due(only={"2"})] == ["b"]


# ------------------------------------------------------------------------------------------------ index integration


def test_index_builder_prefers_synced_text(tmp_path: Path) -> None:
    from lex_agent.ingestion.open_corpora import load_catalog
    from lex_agent.runtime import AgentRuntime

    from .test_orchestrator_and_api import _settings

    cfg = _settings(tmp_path)
    act = parse_act_html(_html("labour_uz.html").replace("йигирма бир", "йигирма тўрт"), lang="uz")
    recs = build_records(act, key="6257288", lex_id="6257288", entry=LABOUR, snapshot="2026-11-21")
    with gzip.open(cfg.corpus_dir / BUNDLES["uz"], "wt", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    (cfg.corpus_dir / CATALOG_OUT).write_text(json.dumps({"documents": [
        {"doc_key": "6257288", "uz_id": "6257288", "ru_id": "6257291", "doc_type": "code",
         "short_uz": "Меҳнат кодекси", "short_ru": "Трудовой кодекс", "title_uz": act.title}]}, ensure_ascii=False),
        encoding="utf-8")
    rt = AgentRuntime.build(cfg)
    rt.build_index()
    parts = rt.bm25_store.get_article("6257288", "217", limit=10)
    uz_parts = [c for c in parts if c.language.value in ("uz_latn", "uz_cyrl")]
    assert uz_parts and all(c.extra.get("source") == "lex_uz_sync" for c in uz_parts)
    assert "тўрт" in uz_parts[0].text
    assert load_catalog(cfg.corpus_dir)["6257288"]["ru_id"] == "6257291"
    # the nightly state file never forces a rebuild
    from lex_agent.ingestion.open_corpora import bundle_fingerprint

    before = bundle_fingerprint(cfg.corpus_dir, cfg.cache_dir)
    (cfg.corpus_dir / STATE_FILE).write_text('{"acts": {}, "runs": [1]}', encoding="utf-8")
    assert bundle_fingerprint(cfg.corpus_dir, cfg.cache_dir) == before
