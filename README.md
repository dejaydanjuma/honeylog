# Honeylog

**Consent-first, on-device memory journal for Bee — private, searchable highlights of your day that never leave your phone.**

[![ci](https://github.com/dejaydanjuma/honeylog/actions/workflows/ci.yml/badge.svg)](https://github.com/dejaydanjuma/honeylog/actions/workflows/ci.yml)

---

## The problem

Wearables that remember your day do it by shipping raw audio and transcripts to the cloud. For a device that clips to your collar and hears everything, that is surveillance dressed as convenience. Users want a memory aid — what did I promise at lunch, where did I park, what was that book — not an archive they can't see or control.

## What Honeylog does

Honeylog keeps capture, transcription, embeddings, and search **on-device**, and syncs only coarse salience buckets under a stated differential-privacy budget. Audio never crosses the phone-to-cloud boundary. Transcripts never leave the phone.

```text
Bee audio -> VAD -> Whisper-tiny -> moment extraction
          -> on-device embedding -> salience score
          -> SQLite + sqlite-vec (local)
          -> optional sync: salience buckets only -> AWS
> All commands above assume you are at the repository root (`honeylog/honeylog`).
