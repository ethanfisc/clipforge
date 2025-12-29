# edit_beats.py - Stage 4: build editorial beats from scene.vision (deterministic, restartable)
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pipeline.contracts.beats import Beat, BeatsRun, Scene
from pipeline.util.jsonio import read_text, write_text, dumps_stable
from pipeline.util.log import RunLogger, _utc_ts


# -------------------------
# Tokenization / TF-IDF
# -------------------------

_EN_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "then",
    "to",
    "with",
    "you",
    "your",
}


def _tokenize(text: str) -> List[str]:
    """Deterministic tokenization, tries to preserve CJK runs."""
    if not text:
        return []
    t = text.strip().lower()

    # ASCII words/numbers + CJK blocks
    toks: List[str] = []
    toks.extend(re.findall(r"[a-z0-9]+", t))
    toks.extend(re.findall(r"[\u4e00-\u9fff]+", t))

    out: List[str] = []
    for tok in toks:
        if not tok:
            continue
        if re.fullmatch(r"[a-z0-9]+", tok):
            if len(tok) < 3:
                continue
            if tok in _EN_STOPWORDS:
                continue
        out.append(tok)
    return out


def _scene_text(scene: Scene) -> str:
    v = scene.vision
    parts: List[str] = []
    if v.summary:
        parts.append(v.summary)
    if v.tags:
        parts.append(" ".join(v.tags))
    if v.text_on_screen:
        parts.append(v.text_on_screen)
    return " ".join(parts)


def _tfidf_vectors(texts: List[str]) -> List[Dict[str, float]]:
    """Video-local TF-IDF (no external model)."""
    tokens_per_doc: List[List[str]] = [_tokenize(t) for t in texts]
    n = len(tokens_per_doc)
    if n == 0:
        return []

    # df
    df: Dict[str, int] = {}
    for toks in tokens_per_doc:
        for tok in set(toks):
            df[tok] = df.get(tok, 0) + 1

    # idf
    idf: Dict[str, float] = {}
    for tok, dfi in df.items():
        idf[tok] = math.log((1.0 + n) / (1.0 + float(dfi))) + 1.0

    vecs: List[Dict[str, float]] = []
    for toks in tokens_per_doc:
        if not toks:
            vecs.append({})
            continue
        tf: Dict[str, int] = {}
        for tok in toks:
            tf[tok] = tf.get(tok, 0) + 1
        denom = float(sum(tf.values())) or 1.0
        v: Dict[str, float] = {}
        for tok, c in tf.items():
            v[tok] = (float(c) / denom) * idf.get(tok, 0.0)
        vecs.append(v)
    return vecs


def _cosine_sparse(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    # dot
    if len(a) > len(b):
        a, b = b, a
    dot = 0.0
    for k, va in a.items():
        vb = b.get(k)
        if vb is not None:
            dot += va * vb
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# -------------------------
# Window selection (contiguous, coherence-first)
# -------------------------


def _select_scene_window(
    scenes: List[Scene],
    vecs: List[Dict[str, float]],
    *,
    min_s: float = 45.0,
    max_s: float = 75.0,
    target_s: float = 60.0,
    prefer_earlier_w: float = 0.02,
    len_w: float = 0.35,
) -> Tuple[int, int, Dict[str, Any]]:
    """Pick a contiguous scene window to hit 45-75s (evidence-based)."""
    n = len(scenes)
    if n == 0:
        return (0, -1, {"mode": "empty"})

    durs = [max(0.0, float(s.duration_s)) for s in scenes]
    conf = [float(s.vision.confidence or 0.0) for s in scenes]
    has_ocr = [1.0 if (s.vision.text_on_screen or "").strip() else 0.0 for s in scenes]
    has_text = [1.0 if vecs[i] else 0.0 for i in range(n)]

    # scene utility score (positive-only, genre-agnostic)
    score = [conf[i] + 0.15 * has_ocr[i] + 0.10 * has_text[i] for i in range(n)]

    best = None
    best_meta: Dict[str, Any] = {}

    for i in range(n):
        dur = 0.0
        sc = 0.0
        for j in range(i, n):
            dur += durs[j]
            sc += score[j]
            if dur > max_s + 1e-9:
                break
            if dur + 1e-9 < min_s:
                continue

            # prefer duration near target
            len_pen = abs(dur - target_s) / (target_s + 1e-9)
            start_pen = float(scenes[i].start_s) / max(1e-9, float(scenes[-1].end_s))
            window_score = sc - len_w * len_pen - prefer_earlier_w * start_pen

            if best is None or window_score > best[0]:
                best = (window_score, i, j, dur, sc)

    if best is None:
        # no window meets min_s; return full (short video)
        meta = {
            "mode": "full",
            "reason": "video_shorter_than_min",
            "min_s": min_s,
            "max_s": max_s,
        }
        return (0, n - 1, meta)

    _, i, j, dur, raw_sc = best
    best_meta = {
        "mode": "window",
        "min_s": min_s,
        "max_s": max_s,
        "target_s": target_s,
        "start_scene": int(scenes[i].scene_id),
        "end_scene": int(scenes[j].scene_id),
        "start_s": float(scenes[i].start_s),
        "end_s": float(scenes[j].end_s),
        "duration_s": float(dur),
        "raw_score": float(raw_sc),
    }
    return (i, j, best_meta)


# -------------------------
# Beat segmentation (DP)
# -------------------------


def _dp_segment(
    scenes: List[Scene],
    vecs: List[Dict[str, float]],
    *,
    k_min: int,
    k_max: int,
    min_beat_s: float,
    max_beat_s: float,
    target_beat_s: float,
    w_dur: float = 1.0,
    w_incoh: float = 0.6,
    w_conf: float = 0.4,
    w_empty: float = 0.25,
    w_boundary: float = 0.35,
    k_pref: Optional[int] = None,
    k_pref_w: float = 0.08,
) -> Tuple[List[Tuple[int, int]], Dict[str, Any]]:
    """Return list of (a,b) indices inclusive within `scenes`."""
    n = len(scenes)
    if n == 0:
        return ([], {"mode": "empty"})

    # signals
    dur = [max(1e-6, float(s.duration_s)) for s in scenes]
    conf = [float(s.vision.confidence or 0.0) for s in scenes]
    empty = [0.0 if vecs[i] else 1.0 for i in range(n)]

    sims = [_cosine_sparse(vecs[i], vecs[i + 1]) for i in range(n - 1)]
    ps_dur = [0.0]
    ps_conf = [0.0]
    ps_empty = [0.0]
    ps_sim = [0.0]
    for i in range(n):
        ps_dur.append(ps_dur[-1] + dur[i])
        ps_conf.append(ps_conf[-1] + conf[i])
        ps_empty.append(ps_empty[-1] + empty[i])
        if i < n - 1:
            ps_sim.append(ps_sim[-1] + sims[i])

    def seg_stats(a: int, b: int) -> Tuple[float, float, float, float]:
        # duration, mean_conf, frac_empty, mean_sim_inside
        seg_dur = ps_dur[b + 1] - ps_dur[a]
        mconf = (ps_conf[b + 1] - ps_conf[a]) / float(b - a + 1)
        fempty = (ps_empty[b + 1] - ps_empty[a]) / float(b - a + 1)
        if b > a:
            msim = (ps_sim[b] - ps_sim[a]) / float(b - a)
        else:
            msim = 0.0
        return seg_dur, mconf, fempty, msim

    BIG = 1e9

    def seg_cost(a: int, b: int) -> float:
        seg_dur, mconf, fempty, msim = seg_stats(a, b)
        if seg_dur + 1e-9 < min_beat_s or seg_dur - 1e-9 > max_beat_s:
            return BIG
        dur_pen = ((seg_dur - target_beat_s) ** 2) / ((target_beat_s**2) + 1e-9)
        incoh_pen = 1.0 - msim
        conf_pen = 1.0 - _clamp(mconf, 0.0, 1.0)
        empty_pen = _clamp(fempty, 0.0, 1.0)
        return (
            w_dur * dur_pen
            + w_incoh * incoh_pen
            + w_conf * conf_pen
            + w_empty * empty_pen
        )

    # Try K in [k_min,k_max] and pick best
    best_total = None
    best_back = None
    best_k = None

    k_min_eff = max(1, min(k_min, n))
    k_max_eff = max(1, min(k_max, n))
    if k_min_eff > k_max_eff:
        k_min_eff = k_max_eff

    for K in range(k_min_eff, k_max_eff + 1):
        # dp[k][j] = min cost to segment first j scenes into k beats
        dp = [[BIG] * (n + 1) for _ in range(K + 1)]
        back = [[-1] * (n + 1) for _ in range(K + 1)]
        dp[0][0] = 0.0

        for k in range(1, K + 1):
            for j in range(1, n + 1):
                # last segment is [i, j-1]
                best = BIG
                best_i = -1
                for i in range(0, j):
                    prev = dp[k - 1][i]
                    if prev >= BIG:
                        continue
                    c = seg_cost(i, j - 1)
                    if c >= BIG:
                        continue
                    # boundary penalty (avoid cutting at high similarity)
                    if j - 1 < n - 1:
                        c += w_boundary * sims[j - 1]
                    cand = prev + c
                    if cand < best:
                        best = cand
                        best_i = i
                dp[k][j] = best
                back[k][j] = best_i

        total = dp[K][n]
        if total >= BIG:
            continue

        # prefer K near k_pref, if provided
        if k_pref is not None:
            total += k_pref_w * float((K - k_pref) ** 2)

        if best_total is None or total < best_total:
            best_total = total
            best_back = back
            best_k = K

    if best_total is None or best_back is None or best_k is None:
        # Fallback: 1 beat = full
        return ([(0, n - 1)], {"mode": "fallback_full", "reason": "dp_failed"})

    # Reconstruct
    K = best_k
    bounds: List[Tuple[int, int]] = []
    j = n
    for k in range(K, 0, -1):
        i = best_back[k][j]
        if i < 0:
            i = 0
        bounds.append((i, j - 1))
        j = i
    bounds.reverse()

    meta = {
        "mode": "dp",
        "K": int(K),
        "k_min": int(k_min),
        "k_max": int(k_max),
        "k_pref": int(k_pref) if k_pref is not None else None,
        "target_beat_s": float(target_beat_s),
        "min_beat_s": float(min_beat_s),
        "max_beat_s": float(max_beat_s),
        "weights": {
            "w_dur": w_dur,
            "w_incoh": w_incoh,
            "w_conf": w_conf,
            "w_empty": w_empty,
            "w_boundary": w_boundary,
            "k_pref_w": k_pref_w,
        },
        "total_cost": float(best_total),
    }
    return (bounds, meta)


# -------------------------
# Beat rendering
# -------------------------


def _beat_priority(scenes: List[Scene], *, is_hook: bool, is_payoff: bool) -> int:
    conf = [float(s.vision.confidence or 0.0) for s in scenes]
    mconf = sum(conf) / max(1, len(conf))
    has_ocr = any((s.vision.text_on_screen or "").strip() for s in scenes)

    score = 0.0
    score += 0.8 * mconf
    score += 0.15 * (1.0 if has_ocr else 0.0)
    score += 0.10 * (1.0 if is_hook else 0.0)
    score += 0.10 * (1.0 if is_payoff else 0.0)

    # map to 1..5
    if score >= 0.80:
        return 5
    if score >= 0.62:
        return 4
    if score >= 0.45:
        return 3
    if score >= 0.28:
        return 2
    return 1


def _beat_summary(scenes: List[Scene]) -> str:
    # Best available scene summary (extractive)
    best = None
    best_conf = -1.0
    for s in scenes:
        summ = (s.vision.summary or "").strip()
        conf = float(s.vision.confidence or 0.0)
        if summ and conf > best_conf:
            best = summ
            best_conf = conf

    ocr_bits: List[str] = []
    for s in scenes:
        t = (s.vision.text_on_screen or "").strip()
        if t:
            ocr_bits.append(t)

    tags: List[str] = []
    for s in scenes:
        for t in s.vision.tags or []:
            tt = str(t).strip()
            if tt:
                tags.append(tt)

    # Deterministic: stable unique preserving order
    def uniq(xs: Iterable[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for x in xs:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    tags_u = uniq(tags)[:6]
    ocr_u = uniq(ocr_bits)[:2]

    parts: List[str] = []
    if best:
        parts.append(best)
    if tags_u:
        parts.append("tags: " + ", ".join(tags_u))
    if ocr_u:
        parts.append("text: " + " | ".join(ocr_u))
    s = " ".join(parts).strip()
    return s[:280]


def edit_beats(
    beats_vision_path: Path,
    *,
    out_path: Optional[Path] = None,
    overwrite: bool = False,
    target_min_s: float = 45.0,
    target_max_s: float = 75.0,
    target_len_s: float = 60.0,
    beats_min: int = 6,
    beats_max: int = 12,
    min_beat_s: float = 2.5,
    max_beat_s: float = 15.0,
    logger: RunLogger | None = None,
) -> Path:
    """Stage 4: beats.vision.json -> beats.edit.json (replaces run.beats[])."""
    beats_vision_path = beats_vision_path.resolve()
    run_dir = beats_vision_path.parent
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "edit_beats.log"
    log = logger or RunLogger(log_path=log_path, verbose=False, progress_enabled=False)

    run = BeatsRun.model_validate_json(read_text(beats_vision_path))

    if out_path is None:
        out_path = beats_vision_path.with_name("beats.edit.json")
    out_path = out_path.resolve()
    if out_path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {out_path}")

    scenes_all = sorted(run.scenes, key=lambda s: int(s.scene_id))
    texts = [_scene_text(s) for s in scenes_all]
    vecs = _tfidf_vectors(texts)

    total_dur = float(run.video.duration_s)

    # 1) pick scene window if needed
    if total_dur > target_max_s + 1.0:
        i0, i1, sel_meta = _select_scene_window(
            scenes_all,
            vecs,
            min_s=target_min_s,
            max_s=target_max_s,
            target_s=target_len_s,
        )
    else:
        i0, i1, sel_meta = (
            0,
            len(scenes_all) - 1,
            {"mode": "full", "duration_s": total_dur},
        )

    scenes = scenes_all[i0 : i1 + 1]
    vecs_sel = vecs[i0 : i1 + 1]
    sel_dur = float(scenes[-1].end_s - scenes[0].start_s) if scenes else 0.0

    # 2) choose target beat duration + K preference
    # For 45-75s shorts, sweet spot is ~6-10s beats.
    target_beat_s = _clamp(sel_dur / 9.0 if sel_dur > 0 else 7.0, 4.0, 10.0)
    k_pref = int(round(sel_dur / target_beat_s)) if sel_dur > 0 else None

    # 3) DP segmentation into 6-12 beats (or fewer if video is too short)
    k_min = beats_min
    k_max = beats_max
    if sel_dur < target_min_s - 1e-6:
        # can't guarantee 6 beats if clip is short; degrade gracefully
        k_max = min(k_max, max(1, int(round(sel_dur / max(3.0, min_beat_s)))))
        k_min = min(k_min, k_max)
        if k_pref is not None:
            k_pref = min(k_pref, k_max)

    bounds, seg_meta = _dp_segment(
        scenes,
        vecs_sel,
        k_min=k_min,
        k_max=k_max,
        min_beat_s=min_beat_s,
        max_beat_s=max_beat_s,
        target_beat_s=target_beat_s,
        k_pref=k_pref,
    )

    # 4) build beats
    beats: List[Beat] = []
    for bi, (a, b) in enumerate(bounds):
        seg_scenes = scenes[a : b + 1]
        if not seg_scenes:
            continue

        is_hook = bi == 0
        is_payoff = bi == (len(bounds) - 1)
        intent = "hook" if is_hook else ("payoff" if is_payoff else "step")

        beats.append(
            Beat(
                beat_id=bi,
                scene_ids=[int(s.scene_id) for s in seg_scenes],
                start_s=float(seg_scenes[0].start_s),
                end_s=float(seg_scenes[-1].end_s),
                summary=_beat_summary(seg_scenes),
                intent=intent,
                priority=_beat_priority(
                    seg_scenes, is_hook=is_hook, is_payoff=is_payoff
                ),
            )
        )

    # 5) write params metadata
    params = dict(run.params or {})
    edit_meta: Dict[str, Any] = {
        "algo": "edit_v1_tfidf_dp",
        "updated_at": _utc_ts(),
        "input": beats_vision_path.name,
        "output": out_path.name,
        "selection": sel_meta,
        "segmentation": seg_meta,
        "targets": {
            "target_min_s": float(target_min_s),
            "target_max_s": float(target_max_s),
            "target_len_s": float(target_len_s),
            "beats_min": int(beats_min),
            "beats_max": int(beats_max),
            "min_beat_s": float(min_beat_s),
            "max_beat_s": float(max_beat_s),
        },
        "counts": {
            "scenes_total": int(len(scenes_all)),
            "scenes_selected": int(len(scenes)),
            "beats": int(len(beats)),
        },
        "selected_duration_s": float(sel_dur),
    }
    params["edit"] = edit_meta
    run.params = params
    run.beats = beats

    # validate
    BeatsRun.model_validate(
        run.model_dump(exclude={"scenes": {"__all__": {"duration_s"}}})
    )

    json_text = run.model_dump_json(
        indent=2,
        exclude={"scenes": {"__all__": {"duration_s"}}},
    )
    write_text(out_path, json_text)

    log.info(
        f"edit_beats: wrote {out_path.name} scenes_selected={len(scenes)} beats={len(beats)} sel_dur={sel_dur:.1f}s"
    )
    log.close()
    return out_path
