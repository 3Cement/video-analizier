from app.errors import classify_job_error


def test_classify_youtube_bot_error():
    err = classify_job_error(Exception("Sign in to confirm you're not a bot"))
    assert err.code == "youtube_bot_check"
    assert "YTDLP_PROXY" in err.hint


def test_classify_network_error():
    err = classify_job_error(Exception("Connection timed out"))
    assert err.code == "network"


def test_classify_duration_error():
    err = classify_job_error(Exception("Video exceeds maximum duration (120 minutes)."))
    assert err.code == "video_too_long"
