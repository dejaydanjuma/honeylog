//! Honeylog core: salience scoring and ranking.
//!
//! Exposed to Kotlin (Android) and Swift (iOS) via uniffi so the ranking
//! cannot drift between platforms.

uniffi::setup_scaffolding!("honeylog");

use serde::{Deserialize, Serialize};

/// Recency decay per day: score multiplies by this for each day of age.
pub const GAMMA: f32 = 0.94;
pub const SECONDS_PER_DAY: f32 = 86_400.0;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, uniffi::Enum)]
#[serde(rename_all = "snake_case")]
pub enum Category {
    Person,
    Commitment,
    Location,
    Object,
    Ambient,
}

impl Category {
    pub fn prior(self) -> f32 {
        match self {
            Category::Commitment => 1.50,
            Category::Person => 1.35,
            Category::Location => 1.20,
            Category::Object => 1.00,
            Category::Ambient => 0.60,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, uniffi::Record)]
pub struct Moment {
    pub embedding: Vec<f32>,
    pub timestamp: u64,
    pub category: Category,
}

fn cosine(a: &[f32], b: &[f32]) -> f32 {
    debug_assert_eq!(a.len(), b.len());
    let (mut dot, mut na, mut nb) = (0.0_f32, 0.0_f32, 0.0_f32);
    for (x, y) in a.iter().zip(b) {
        dot += x * y;
        na += x * x;
        nb += y * y;
    }
    let denom = (na.sqrt() * nb.sqrt()).max(f32::EPSILON);
    dot / denom
}

// ---- internal, reference-based (used by tests and by the FFI wrappers) ----

pub fn score_moment(query: &[f32], moment: &Moment, now: u64) -> f32 {
    assert_eq!(query.len(), moment.embedding.len(), "dim mismatch");
    let relevance = cosine(query, &moment.embedding);
    let days = now.saturating_sub(moment.timestamp) as f32 / SECONDS_PER_DAY;
    let recency = GAMMA.powf(days);
    relevance * recency * moment.category.prior()
}

pub fn rank(query: &[f32], moments: &[Moment], now: u64, k: usize) -> Vec<usize> {
    let mut scored: Vec<(usize, f32)> = moments
        .iter()
        .enumerate()
        .map(|(i, m)| (i, score_moment(query, m, now)))
        .collect();
    scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    scored.into_iter().take(k).map(|(i, _)| i).collect()
}

// ---- FFI surface (owned types; usize is not FFI-safe) ----

#[uniffi::export(name = "score_moment")]
pub fn score_moment_ffi(query: Vec<f32>, moment: Moment, now: u64) -> f32 {
    score_moment(&query, &moment, now)
}

#[uniffi::export(name = "rank")]
pub fn rank_ffi(query: Vec<f32>, moments: Vec<Moment>, now: u64, k: u32) -> Vec<u32> {
    rank(&query, &moments, now, k as usize)
        .into_iter()
        .map(|i| i as u32)
        .collect()
}

// ---- tests (unchanged) ----

#[cfg(test)]
mod tests {
    use super::*;

    fn unit(v: &[f32]) -> Vec<f32> {
        let n = v.iter().map(|x| x * x).sum::<f32>().sqrt();
        v.iter().map(|x| x / n).collect()
    }

    fn m(emb: Vec<f32>, ts: u64, cat: Category) -> Moment {
        Moment { embedding: emb, timestamp: ts, category: cat }
    }

    #[test]
    fn cosine_of_identical_is_one() {
        let v = unit(&[1.0, 2.0, 3.0]);
        assert!((cosine(&v, &v) - 1.0).abs() < 1e-5);
    }

    #[test]
    fn cosine_of_orthogonal_is_zero() {
        assert!(cosine(&[1.0, 0.0], &[0.0, 1.0]).abs() < 1e-6);
    }

    #[test]
    fn recency_decays_monotonically() {
        let q = unit(&[1.0, 0.0, 0.0]);
        let now = 1_000_000;
        let fresh = m(q.clone(), now, Category::Ambient);
        let old = m(q.clone(), now - 7 * 86_400, Category::Ambient);
        assert!(score_moment(&q, &fresh, now) > score_moment(&q, &old, now));
    }

    #[test]
    fn one_day_ratio_equals_gamma() {
        let q = unit(&[1.0, 0.0]);
        let now = 86_400;
        let fresh = m(q.clone(), now, Category::Ambient);
        let day_old = m(q.clone(), 0, Category::Ambient);
        let ratio = score_moment(&q, &day_old, now) / score_moment(&q, &fresh, now);
        assert!((ratio - GAMMA).abs() < 1e-4);
    }

    #[test]
    fn commitment_beats_ambient_at_equal_relevance() {
        let q = unit(&[1.0, 0.0]);
        let now = 1000;
        let c = m(q.clone(), now, Category::Commitment);
        let a = m(q.clone(), now, Category::Ambient);
        assert!(score_moment(&q, &c, now) > score_moment(&q, &a, now));
    }

    #[test]
    fn rank_returns_top_k_descending() {
        let q = unit(&[1.0, 0.0]);
        let now = 1000;
        let moments = vec![
            m(unit(&[0.0, 1.0]), now, Category::Ambient),
            m(unit(&[1.0, 0.0]), now, Category::Ambient),
            m(unit(&[0.7, 0.7]), now, Category::Person),
        ];
        assert_eq!(rank(&q, &moments, now, 2), vec![2, 1]);
    }

    #[test]
    fn rank_clamps_k_to_len() {
        let q = unit(&[1.0]);
        let moments = vec![m(unit(&[1.0]), 0, Category::Ambient)];
        assert_eq!(rank(&q, &moments, 1000, 10).len(), 1);
    }

    #[test]
    #[should_panic(expected = "dim mismatch")]
    fn dim_mismatch_panics() {
        let q = vec![1.0, 0.0];
        let bad = m(vec![1.0], 0, Category::Ambient);
        score_moment(&q, &bad, 0);
    }
}