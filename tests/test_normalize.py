from logscope.normalize import normalize_message


def test_numbers_collapse():
    assert normalize_message("retry 3 of 5 failed") == "retry <n> of <n> failed"


def test_same_error_different_ids_normalize_equal():
    a = normalize_message("connection to 10.0.0.5 timed out after 30s")
    b = normalize_message("connection to 192.168.1.9 timed out after 45s")
    assert a == b == "connection to <ip> timed out after <n>"


def test_uuid_collapses():
    assert normalize_message("job 550e8400-e29b-41d4-a716-446655440000 failed") == \
        "job <uuid> failed"


def test_hex_collapses():
    assert normalize_message("bad pointer 0xdeadbeef in module") == \
        "bad pointer <hex> in module"


def test_quoted_strings_collapse():
    a = normalize_message("file 'report.csv' not found")
    b = normalize_message('file "data.json" not found')
    assert a == b == "file <str> not found"


def test_different_messages_stay_different():
    assert normalize_message("disk full") != normalize_message("out of memory")


def test_whitespace_is_collapsed():
    assert normalize_message("too   many\tspaces") == "too many spaces"


def test_paths_collapse():
    assert normalize_message("open /var/log/app/server.log failed") == \
        "open <path> failed"
