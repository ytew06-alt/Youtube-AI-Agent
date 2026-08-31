from functions.extract_from_youtube import (
    get_chunks, normalise_youtube_url, CHUNK_THRESHOLD, CHUNK_SIZE, OVERLAP
)


def test_short_video_single_chunk():
    assert get_chunks(300) == [(0, 300)]
    assert get_chunks(30) == [(0, 30)]


def test_exact_threshold_boundary():
    assert get_chunks(CHUNK_THRESHOLD) == [(0, CHUNK_THRESHOLD)]
    assert len(get_chunks(CHUNK_THRESHOLD + 1)) > 1


def test_chunks_cover_whole_video():
    chunks = get_chunks(3600)
    assert chunks[0][0] == 0
    assert chunks[-1][1] == 3600


def test_chunks_never_exceed_duration():
    for d in (901, 1500, 3600, 7200):
        assert all(end <= d for _, end in get_chunks(d))


def test_overlap_is_correct():
    chunks = get_chunks(3600)
    for i in range(len(chunks) - 1):
        assert chunks[i][1] - chunks[i + 1][0] == OVERLAP


def test_all_values_are_ints():
    """Guards the tuple-unpacking bug: offsets must format as '300s'."""
    for start, end in get_chunks(3600):
        assert isinstance(start, int) and isinstance(end, int)
        assert f"{start}s".replace("s", "").isdigit()


def test_url_normalisation():
    vid = "https://www.youtube.com/watch?v=RGOj5yH7evk"
    assert normalise_youtube_url("https://www.youtube.com/watch?v=RGOj5yH7evk&t=3s") == vid
    assert normalise_youtube_url("https://youtu.be/RGOj5yH7evk") == vid
    assert normalise_youtube_url("https://www.youtube.com/watch?v=RGOj5yH7evk&list=PLabc") == vid
    assert normalise_youtube_url(vid) == vid