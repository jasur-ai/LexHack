"""Train the lightweight CPU reranker on automatically generated question→article pairs.

Training data (no manual labelling needed beyond the dev split of the gold set):

* **title questions** — article titles of the codes and frequently used laws, rewritten the way people ask
  (Latin script for Uzbek, inflected words dropped or changed, question frames, light typos);
* **content questions** — a handful of the most informative words of an article's first sentence;
* **situation questions** — the formal wording of every situation in the lexicon, pointing at its first target;
* the **dev split** of ``eval/retrieval_gold.jsonl`` (the ``test`` split is never used here).

For every question the real first-stage retriever produces candidates; each candidate gets the same feature
vector the runtime reranker computes, labelled 1 when it is an expected article. A LightGBM LambdaRank model is
fitted and exported with ``Booster.dump_model()`` to ``lex_agent/data/reranker_model.json``; the agent evaluates
it in pure Python, so LightGBM is only needed here (``pip install -e .[train]``).

Usage::

    python scripts/train_reranker.py                 # train, evaluate on dev/test, write the model
    python scripts/train_reranker.py --queries 4000  # smaller synthetic set
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import re
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lex_agent.chunk_text import chunk_article_id, display_text  # noqa: E402
from lex_agent.config import get_settings  # noqa: E402
from lex_agent.evaluation import _matches, evaluate_retrieval, load_gold  # noqa: E402
from lex_agent.knowledge.lexicon import get_lexicon  # noqa: E402
from lex_agent.retrieval.reranker import FEATURE_NAMES, MODEL_PATH, TreeEnsemble  # noqa: E402
from lex_agent.runtime import AgentRuntime  # noqa: E402

UZ_FRAMES = [
    "{t}", "{t}", "{t} qanday?", "{t} nima?", "{t} haqida", "{t} qanday tartibda?", "{t} mumkinmi?",
    "{t} qachon?", "{t} kimga tegishli?", "{t} bo'yicha qonun nima deydi?", "{t} qancha?",
]
RU_FRAMES = [
    "{t}", "{t}", "{t} — что говорит закон?", "Какой {t}?", "{t} порядок", "Как {t}?", "{t} сроки",
    "Подскажите про {t}", "{t} кому положено?",
]
UZ_STOP = {"va", "yoki", "hamda", "bilan", "uchun", "boʻyicha", "bo'yicha", "toʻgʻrisidagi", "to'g'risidagi",
           "ushbu", "oid", "doir", "boʻlgan", "bo'lgan", "etish", "qilish", "hollar", "tartibi", "umumiy", "qoidalar"}
RU_STOP = {"и", "или", "в", "на", "о", "об", "по", "для", "с", "со", "к", "от", "при", "порядок", "общие", "положения"}
_SPLIT = re.compile(r"[\s,.;:()«»\"]+")


def typo(word: str, rng: random.Random) -> str:
    if len(word) < 5 or not word.isalpha():
        return word
    i = rng.randrange(1, len(word) - 1)
    op = rng.random()
    if op < 0.35:
        return word[:i] + word[i + 1:]  # deletion
    if op < 0.7:
        return word[:i] + word[i + 1] + word[i] + word[i + 2:]  # transposition
    return word[:i] + word[i] + word[i:]  # duplication


def strip_uz(word: str, rng: random.Random) -> str:
    for suf in ("larining", "lariga", "laridan", "larini", "ining", "ning", "ini", "ga", "dan", "da", "ni"):
        if word.endswith(suf) and len(word) - len(suf) >= 4 and rng.random() < 0.5:
            return word[: -len(suf)]
    return word


def title_question(title: str, lang: str, rng: random.Random) -> str | None:
    words = [w for w in _SPLIT.split(title) if w]
    stop = RU_STOP if lang == "ru" else UZ_STOP
    content = [w for w in words if w.lower() not in stop]
    if len(content) < 2:
        return None
    keep = content if len(content) <= 4 else [w for w in content if rng.random() > 0.3] or content[:3]
    keep = keep[:7]
    if lang != "ru":
        keep = [strip_uz(w.lower(), rng) for w in keep]
    else:
        keep = [w.lower() for w in keep]
    if rng.random() < 0.15:
        j = rng.randrange(len(keep))
        keep[j] = typo(keep[j], rng)
    if lang != "ru" and rng.random() < 0.3:
        keep = [w.replace("'", "").replace("ʻ", "").replace("ʼ", "") for w in keep]
    frame = rng.choice(RU_FRAMES if lang == "ru" else UZ_FRAMES)
    q = frame.format(t=" ".join(keep))
    return q[:1].upper() + q[1:]


def content_question(text: str, lang: str, idf: dict[str, float], rng: random.Random) -> str | None:
    first = re.split(r"(?<=[.;!?])\s", text.strip(), maxsplit=1)[0]
    words = [w for w in _SPLIT.split(first) if len(w) > 3 and w.isalpha()]
    if len(words) < 4:
        return None
    scored = sorted(set(words), key=lambda w: -idf.get(w.lower(), 0.0))
    pick = scored[: rng.randint(3, 6)]
    rng.shuffle(pick)
    q = " ".join(w.lower() for w in pick)
    if lang != "ru" and rng.random() < 0.5:
        q += rng.choice([" qanday", " nima", " qachon", " mumkinmi"])
    elif lang == "ru" and rng.random() < 0.5:
        q += rng.choice([" как", " когда", " можно ли"])
    return q


def gather_synthetic(rt: AgentRuntime, n_queries: int, seed: int) -> list[tuple[str, list[list]]]:
    rng = random.Random(seed)
    store = rt.bm25_store
    catalog = rt.retriever.act_resolver.catalog
    popular = [k for k, d in catalog.items() if d.get("doc_type") in ("code", "constitution")]
    laws = [k for k, d in catalog.items() if d.get("doc_type") not in ("code", "constitution") and d.get("articles_uz", 0) >= 8]
    out: list[tuple[str, list[list]]] = []
    articles: list[tuple[str, str, str, str, str]] = []  # doc, art, lang, title, text
    with store._connect() as conn:
        rows = conn.execute(
            "SELECT canonical_id, article_id, language, chunk_json FROM chunks "
            "WHERE article_id IS NOT NULL AND chunk_id NOT LIKE '%#%' OR chunk_id LIKE '%#1'"
        ).fetchall()
    from lex_agent.retrieval.bm25_store import unpack_chunk

    wanted_docs = set(popular) | set(laws)
    for r in rows:
        if r["canonical_id"] not in wanted_docs or not r["article_id"]:
            continue
        c = unpack_chunk(r["chunk_json"])
        title = c.article_title or ""
        if not title:
            continue
        lang = c.language.value
        if lang == "uz_cyrl":
            title = display_text(title, "uz_cyrl", "uz_latn")
            lang = "uz_latn"
        body = c.text.partition("\n")[2] or c.text
        articles.append((c.canonical_id, chunk_article_id(c), lang, title, body))
    rng.shuffle(articles)
    # Codes are what people ask about most: oversample them
    code_set = set(popular)
    articles.sort(key=lambda a: 0 if a[0] in code_set and rng.random() < 0.6 else 1)
    idf_cache: dict[str, float] = {}
    for doc, art, lang, title, body in articles:
        if len(out) >= n_queries:
            break
        expect = [[doc, [art]]]
        if rng.random() < 0.7:
            q = title_question(title, lang, rng)
        else:
            words = {w.lower() for w in _SPLIT.split(body[:300]) if w.isalpha()}
            missing = [w for w in words if w not in idf_cache]
            if missing:
                from lex_agent.language.textproc import query_terms

                for w in missing:
                    terms = query_terms(w, language=lang)
                    idf_cache[w] = store.idf(terms).get(terms[0], 0.0) if terms else 0.0
            q = content_question(display_text(body, "uz_cyrl", "uz_latn") if lang == "uz_latn" else body, lang, idf_cache, rng)
        if q:
            out.append((q, expect))
    # Situation lexicon: the formal wording of each situation points at its main norms
    for concept in get_lexicon().concepts:
        if concept.targets:
            top = concept.targets[0]
            out.append((concept.formal_uz, [[top[0], [top[1]]]]))
            out.append((concept.formal_ru, [[top[0], [top[1]]]]))
    return out


async def build_groups(rt: AgentRuntime, items: list[tuple[str, list[list]]], *, max_cands: int = 60):
    """Feature groups for questions: one group per question whose candidates contain a positive and a negative."""
    retr = rt.retriever
    groups: list[tuple[list[list[float]], list[int]]] = []
    skipped = 0
    for q, expect in items:
        qa = retr.analyze(q)
        cands, qinfo = await retr.candidates(qa, top_k=12)
        cands = cands[:max_cands]
        labels = [1 if _matches(c, expect) else 0 for c in cands]
        if not cands or not any(labels) or all(labels):
            skipped += 1
            groups.append(([], []))
            continue
        groups.append((retr.reranker.features(qinfo, cands), labels))
    return groups, skipped


def flatten(groups: list[tuple[list[list[float]], list[int]]], weight: int = 1):
    X: list[list[float]] = []
    y: list[int] = []
    sizes: list[int] = []
    for _ in range(weight):
        for feats, labels in groups:
            if feats:
                X.extend(feats)
                y.extend(labels)
                sizes.append(len(labels))
    return X, y, sizes


def offline_hit1(groups, score_fn) -> float:
    """Share of questions whose best-scored candidate is a correct article (ranking only, no dedupe)."""
    total = hits = 0
    for feats, labels in groups:
        if not feats:
            continue
        total += 1
        scores = [score_fn(f) for f in feats]
        best = max(range(len(scores)), key=lambda i: scores[i])
        hits += labels[best]
    return hits / max(total, 1)


def train_model(lgb, np, train_groups, val_groups, *, leaves: int, rounds: int, seed: int, weight_dev: int,
                dev_groups) -> tuple[object, int]:
    Xs, ys, gs = flatten(train_groups)
    Xd, yd, gd = flatten(dev_groups, weight_dev)
    X = Xs + Xd
    y = ys + yd
    g = gs + gd
    increasing = {
        "bm25_norm", "bm25_rank_inv", "exp_rank_inv", "scoped_rank_inv", "syn_rank_inv", "rrf", "dense", "cov_body",
        "cov_art_title",
        "cov_heading", "cov_doc_title", "art_title_precision", "cov_all", "matched_ratio", "exp_cov_title",
        "exp_cov_body", "art_mention", "act_mention", "doc_number_mention", "concept_target", "concept_doc",
        "lang_match",
    }
    decreasing = {"definitions", "repealed", "title_extra"}
    monotone = [1 if f in increasing else -1 if f in decreasing else 0 for f in FEATURE_NAMES]
    params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "ndcg_eval_at": [1, 3],
        "monotone_constraints": monotone,
        "monotone_constraints_method": "advanced",
        "learning_rate": 0.05,
        "num_leaves": leaves,
        "min_data_in_leaf": 30,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "lambda_l2": 1.0,
        "verbose": -1,
        "seed": seed,
        "deterministic": True,
        "num_threads": 2,
    }
    train = lgb.Dataset(np.array(X, dtype=float), label=np.array(y), group=g, feature_name=list(FEATURE_NAMES))
    callbacks = [lgb.log_evaluation(0)]
    valid_sets = []
    if val_groups:
        Xv, yv, gv = flatten(val_groups)
        valid_sets = [lgb.Dataset(np.array(Xv, dtype=float), label=np.array(yv), group=gv, reference=train)]
        callbacks.append(lgb.early_stopping(40, verbose=False))
    booster = lgb.train(params, train, num_boost_round=rounds, valid_sets=valid_sets, callbacks=callbacks)
    best = booster.best_iteration or rounds
    return booster, best


def compact_dump(dump: dict) -> dict:
    keep = {"split_feature", "threshold", "decision_type", "default_left", "left_child", "right_child", "leaf_value"}

    def prune(node: dict) -> dict:
        if "leaf_value" in node:
            return {"leaf_value": round(float(node["leaf_value"]), 6)}
        out = {k: v for k, v in node.items() if k in keep}
        out["threshold"] = float(out["threshold"])
        out["left_child"] = prune(node["left_child"])
        out["right_child"] = prune(node["right_child"])
        return out

    return {
        "feature_names": dump["feature_names"],
        "tree_info": [{"tree_structure": prune(t["tree_structure"])} for t in dump["tree_info"]],
    }


async def main_async(args: argparse.Namespace) -> None:
    import lightgbm as lgb
    import numpy as np

    from lex_agent.retrieval.reranker import heuristic_score

    settings = get_settings()
    rt = AgentRuntime.build(settings)
    rt.build_index()
    # Train against the heuristic first stage (the trained model must not influence its own data)
    rt.retriever.reranker.trees = None

    t0 = time.time()
    synthetic = gather_synthetic(rt, args.queries, args.seed)
    dev_rows = load_gold(split="dev")
    dev = [(r["q"], r["expect"]) for r in dev_rows]
    print(f"synthetic questions: {len(synthetic)}, dev gold: {len(dev)} ({time.time() - t0:.1f}s)")
    syn_groups, syn_skipped = await build_groups(rt, synthetic)
    dev_groups, dev_skipped = await build_groups(rt, dev)
    print(f"groups: synthetic {len(syn_groups) - syn_skipped} (skipped {syn_skipped}), "
          f"dev {len(dev_groups) - dev_skipped} (skipped {dev_skipped}) ({time.time() - t0:.1f}s)")

    # ---------------------------------------------------------------- k-fold model selection on the dev split
    rng = random.Random(args.seed)
    order = list(range(len(dev_groups)))
    rng.shuffle(order)
    folds = [order[i:: args.folds] for i in range(args.folds)]
    heuristic_cv = [offline_hit1([dev_groups[i] for i in f], heuristic_score) for f in folds]
    print(f"heuristic CV hit@1: {sum(heuristic_cv) / len(heuristic_cv):.3f}")
    configs = [(leaves, n_syn, w) for leaves in (7, 15) for n_syn in (0, 1500, len(syn_groups)) for w in (2, 4)]
    results = []
    for leaves, n_syn, w in configs:
        scores = []
        for f in folds:
            held = set(f)
            train_dev = [dev_groups[i] for i in order if i not in held]
            model, best = train_model(lgb, np, syn_groups[:n_syn], [], leaves=leaves, rounds=args.rounds_cv,
                                      seed=args.seed, weight_dev=w, dev_groups=train_dev)
            ens = TreeEnsemble(compact_dump(model.dump_model()))
            scores.append(offline_hit1([dev_groups[i] for i in f], ens.predict))
        mean = sum(scores) / len(scores)
        results.append((mean, leaves, n_syn, w))
        print(f"  leaves={leaves:2d} synthetic={n_syn:5d} dev_weight={w}: CV hit@1 {mean:.3f}")
    best_cv, leaves, n_syn, w = max(results)
    base_cv = sum(heuristic_cv) / len(heuristic_cv)
    print(f"best config: leaves={leaves} synthetic={n_syn} dev_weight={w} (CV {best_cv:.3f} vs heuristic {base_cv:.3f})")

    # ---------------------------------------------------------------- final model on everything but the test split
    model, best = train_model(lgb, np, syn_groups[:n_syn], [], leaves=leaves, rounds=args.rounds, seed=args.seed,
                              weight_dev=w, dev_groups=dev_groups)
    dump = model.dump_model()
    compact = compact_dump(dump)
    importance = dict(zip(FEATURE_NAMES, model.feature_importance("gain").round(1).tolist()))

    rt.retriever.reranker.trees = TreeEnsemble(compact)
    report_test = await evaluate_retrieval(rt.retriever, split="test")
    report_hold = await evaluate_retrieval(rt.retriever, split="holdout")
    report_dev = await evaluate_retrieval(rt.retriever, split="dev")
    rt.retriever.reranker.trees = None
    base_test = await evaluate_retrieval(rt.retriever, split="test")
    base_hold = await evaluate_retrieval(rt.retriever, split="holdout")
    print(f"heuristic  test: hit@1 {base_test['hit@1']} hit@5 {base_test['hit@5']} | holdout: {base_hold['hit@1']} / {base_hold['hit@5']}")
    print(f"trained    test: hit@1 {report_test['hit@1']} hit@5 {report_test['hit@5']} | holdout: {report_hold['hit@1']} / "
          f"{report_hold['hit@5']}  (dev, seen: {report_dev['hit@1']})")

    compact["lexhack_meta"] = {
        "trained": date.today().isoformat(),
        "objective": "lambdarank",
        "trees": len(compact["tree_info"]),
        "config": {"leaves": leaves, "synthetic_questions": n_syn, "dev_weight": w},
        "dev_questions": len(dev),
        "metrics": {
            "cv_dev_hit@1": round(best_cv, 3),
            "cv_dev_hit@1_heuristic": round(base_cv, 3),
            "test": {"hit@1": report_test["hit@1"], "hit@5": report_test["hit@5"]},
            "heuristic_test": {"hit@1": base_test["hit@1"], "hit@5": base_test["hit@5"]},
            "holdout": {"hit@1": report_hold["hit@1"], "hit@5": report_hold["hit@5"]},
            "heuristic_holdout": {"hit@1": base_hold["hit@1"], "hit@5": base_hold["hit@5"]},
        },
        "feature_importance_gain": importance,
    }
    if best_cv < base_cv + args.min_gain:
        print(f"trained model does not beat the heuristic by {args.min_gain} in cross-validation: model not written")
    elif args.dry_run:
        print("dry run: model not written")
    else:
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        MODEL_PATH.write_text(json.dumps(compact, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"model written to {MODEL_PATH} ({MODEL_PATH.stat().st_size / 1024:.0f} KB)")
    top = sorted(importance.items(), key=lambda kv: -kv[1])[:12]
    print("top features:", ", ".join(f"{k}={v:.0f}" for k, v in top))
    await rt.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--queries", type=int, default=5000, help="number of synthetic questions")
    ap.add_argument("--rounds", type=int, default=250, help="boosting rounds of the final model")
    ap.add_argument("--rounds-cv", type=int, default=250, help="boosting rounds during cross-validation")
    ap.add_argument("--folds", type=int, default=5, help="cross-validation folds over the dev split")
    ap.add_argument("--min-gain", type=float, default=0.01, help="required CV hit@1 gain over the heuristic")
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--dry-run", action="store_true", help="evaluate without writing the model file")
    args = ap.parse_args()
    if not math.isfinite(args.queries) or args.queries < 100:
        raise SystemExit("--queries must be at least 100")
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
