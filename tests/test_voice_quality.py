from backend.voice_quality import (
    infer_podcast_voice_profile,
    score_podcast_voice_listenability,
    score_target_range,
)


def test_target_range_rewards_ideal_values_and_rejects_extremes():
    assert score_target_range(130, 95, 112, 155, 178) == 100.0
    assert score_target_range(200, 95, 112, 155, 178) == 0.0


def test_voice_profile_uses_episode_context():
    assert infer_podcast_voice_profile(title="A narrative journey through space") == "storytelling"
    assert infer_podcast_voice_profile(voice_context={"format": "interview"}) == "interview"


def test_listenability_requires_measured_audio():
    result = score_podcast_voice_listenability({})
    assert result["status"] == "not_measured"
    assert result["listenability_score"] is None


def test_balanced_neural_voice_passes_the_listenability_gate():
    result = score_podcast_voice_listenability(
        {
            "word_count": 130,
            "provider": "chatterbox-neural",
            "voice_clarity": {
                "duration_seconds": 60,
                "score": 98,
                "pause_ratio": 0.20,
                "dynamic_range_db": 10,
                "rms_dbfs": -20,
                "peak_dbfs": -5,
                "zero_crossing_rate": 0.07,
                "resonance_score": 95,
                "articulation_score": 95,
                "resonance_low_mid_ratio": 0.30,
                "articulation_high_freq_ratio": 0.10,
                "source_provider": "chatterbox-neural",
            },
        },
        voice_context={"format": "interview"},
    )

    assert result["status"] == "pass"
    assert result["listenability_score"] >= 82
    assert result["confidence"] == "high"
