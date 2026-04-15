from pathlib import Path
from pbrew.fpm.pools import (
    generate_pool_config,
    pool_config_path,
    write_pool_config,
)

PREFIX = Path("/opt/pbrew")


def test_generate_pool_config_contains_user():
    content = generate_pool_config("alice", "8.4", PREFIX)
    assert "[alice]" in content
    assert "user = alice" in content


def test_generate_pool_config_socket_path():
    content = generate_pool_config("alice", "8.4", PREFIX)
    assert "php84-alice.sock" in content


def test_generate_pool_config_debug_suffix():
    content = generate_pool_config("alice", "8.4", PREFIX, debug=True)
    assert "[alice-debug]" in content
    assert "php84d-alice.sock" in content


def test_generate_pool_config_custom_defaults():
    content = generate_pool_config(
        "alice", "8.4", PREFIX,
        pool_defaults={"pm_max_children": 10},
    )
    assert "pm.max_children = 10" in content


def test_pool_config_path_normal():
    path = pool_config_path(PREFIX, "8.4", "alice")
    assert path == PREFIX / "etc" / "fpm" / "8.4" / "php-fpm.d" / "alice.conf"


def test_pool_config_path_debug():
    path = pool_config_path(PREFIX, "8.4", "alice", debug=True)
    assert path == PREFIX / "etc" / "fpm" / "8.4d" / "php-fpm.d" / "alice.conf"


def test_write_pool_config_creates_file(tmp_path):
    path = write_pool_config(tmp_path, "alice", "8.4")
    assert path.exists()
    assert "[alice]" in path.read_text()


def test_write_pool_config_does_not_overwrite(tmp_path):
    path = write_pool_config(tmp_path, "alice", "8.4")
    path.write_text("custom content")
    write_pool_config(tmp_path, "alice", "8.4")
    assert path.read_text() == "custom content"
