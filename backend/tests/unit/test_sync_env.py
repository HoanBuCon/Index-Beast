"""`make env`: thêm biến thiếu vào .env, hỏi khi có biến thừa, không bao giờ sửa dòng cũ hay in giá trị.

Phụ trách: TV1 · [S3] Script đồng bộ .env
"""

from datetime import date

import pytest

from core.config import REPO_ROOT
from scripts import sync_env

EXAMPLE = """# Cấu hình mẫu
# Môi trường: dev | prod
ENVIRONMENT=dev
# Cổng API
API_PORT=18000
# Mật khẩu, phải điền
DB_PASSWORD=change-me
TOKEN_EMPTY=
# Tùy chọn
# OPTIONAL_FLAG=true
"""


def write(path, text):
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write(text)


def read(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return stream.read()


@pytest.fixture
def files(tmp_path):
    example = tmp_path / ".env.example"
    write(example, EXAMPLE)
    return tmp_path / ".env", example


def run(files, *args):
    env, example = files
    return sync_env.main(["--env", str(env), "--example", str(example), *args])


def test_creates_env_from_example_when_missing(files, capsys):
    env, _ = files
    assert run(files) == 0
    assert read(env) == EXAMPLE
    assert "DB_PASSWORD" in capsys.readouterr().out  # nhắc biến còn change-me


def test_appends_only_missing_keys_and_keeps_every_existing_line(files, capsys):
    env, _ = files
    original = "# ghi chú của tôi\nENVIRONMENT=prod\nSECRET_VALUE_XYZ=hunter2\n\nAPI_PORT=19999\n"
    write(env, original)
    run(files, "--keep-extra")  # SECRET_VALUE_XYZ là biến thừa: không hỏi
    result = read(env)
    assert result.startswith(original)  # dòng cũ, thứ tự, giá trị đều nguyên vẹn
    assert "ENVIRONMENT=prod" in result and result.count("API_PORT=") == 1
    appended = result[len(original) :]
    assert "DB_PASSWORD=change-me" in appended and "TOKEN_EMPTY=" in appended
    assert "# Mật khẩu, phải điền" in appended  # chú thích mẫu đi kèm
    assert "ENVIRONMENT=dev" not in result  # không thêm lại biến đã có với giá trị mẫu
    out = capsys.readouterr().out
    assert "DB_PASSWORD" in out and "hunter2" not in out and "19999" not in out


def test_second_run_changes_nothing(files):
    env, _ = files
    write(env, "ENVIRONMENT=dev\n")
    run(files)
    first = read(env)
    run(files)
    assert read(env) == first


def test_commented_optional_keys_are_neither_added_nor_flagged(files, capsys):
    env, _ = files
    write(env, EXAMPLE.replace("# OPTIONAL_FLAG=true", "OPTIONAL_FLAG=false"))
    run(files, "--remove-extra")
    assert "OPTIONAL_FLAG=false" in read(env)  # bật biến tùy chọn không bị coi là thừa
    assert "OPTIONAL_FLAG" not in capsys.readouterr().out.split("Giữ lại")[0]

    other = env.with_name("other.env")
    write(other, "ENVIRONMENT=dev\n")
    sync_env.main(["--env", str(other), "--example", str(files[1])])
    assert "OPTIONAL_FLAG" not in read(other)


def test_extra_keys_are_listed_and_kept_by_default_when_nothing_can_be_asked(files, monkeypatch, capsys):
    env, _ = files
    write(env, EXAMPLE + "OLD_KEY=old-secret\n")
    monkeypatch.setattr("builtins.input", lambda _prompt: (_ for _ in ()).throw(EOFError()))
    run(files)
    assert "OLD_KEY=old-secret" in read(env)
    out = capsys.readouterr().out
    assert "OLD_KEY" in out and "old-secret" not in out


@pytest.mark.parametrize(
    "answers,kept,removed",
    [
        (["y", "n"], {"B_KEY"}, {"A_KEY"}),
        (["", ""], {"A_KEY", "B_KEY"}, set()),  # Enter = giữ
        (["a"], set(), {"A_KEY", "B_KEY"}),
        (["k"], {"A_KEY", "B_KEY"}, set()),
        (["n", "a"], {"A_KEY"}, {"B_KEY"}),
    ],
)
def test_interactive_choice_per_extra_key(files, monkeypatch, answers, kept, removed):
    env, _ = files
    write(env, EXAMPLE + "A_KEY=1\nB_KEY=2\n")
    replies = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(replies))
    run(files)
    result = read(env)
    for key in kept:
        assert f"{key}=" in result
    for key in removed:
        assert f"{key}=" not in result
    assert "ENVIRONMENT=dev" in result  # biến khác không bị đụng
    assert env.with_name(".env.bak").exists() is bool(removed)


def test_remove_extra_flag_backs_up_and_removes_only_the_assignment_lines(files):
    env, _ = files
    before = EXAMPLE + "# ghi chú giữ lại\nOLD_KEY=1\nexport OLD_KEY=2\nKEEP_ME_NOT=3\n"
    write(env, before)
    run(files, "--remove-extra")
    after = read(env)
    assert "OLD_KEY" not in after and "KEEP_ME_NOT" not in after
    assert "# ghi chú giữ lại" in after
    assert read(env.with_name(".env.bak")) == before


def test_keep_extra_flag_never_asks(files, monkeypatch):
    env, _ = files
    write(env, EXAMPLE + "OLD_KEY=1\n")

    def refuse(_prompt):
        raise AssertionError("không được hỏi")

    monkeypatch.setattr("builtins.input", refuse)
    run(files, "--keep-extra")
    assert "OLD_KEY=1" in read(env)


def test_dry_run_writes_nothing_and_asks_nothing(files, monkeypatch):
    env, _ = files
    write(env, "ENVIRONMENT=dev\nOLD_KEY=1\n")
    monkeypatch.setattr("builtins.input", lambda _prompt: (_ for _ in ()).throw(AssertionError("không được hỏi")))
    run(files, "--dry-run")
    assert read(env) == "ENVIRONMENT=dev\nOLD_KEY=1\n" and not env.with_name(".env.bak").exists()

    missing_env = env.with_name("absent.env")
    sync_env.main(["--env", str(missing_env), "--example", str(files[1]), "--dry-run"])
    assert not missing_env.exists()


def test_crlf_and_missing_final_newline_are_preserved(files):
    env, _ = files
    write(env, "ENVIRONMENT=dev\r\nAPI_PORT=1")  # CRLF, không có xuống dòng cuối
    run(files)
    result = read(env)
    assert result.startswith("ENVIRONMENT=dev\r\nAPI_PORT=1\r\n")
    assert "\n" not in result.replace("\r\n", "")  # không lẫn LF trần
    assert result.endswith("\r\n")


def test_bom_and_spaces_around_equals_are_understood(files):
    env, _ = files
    write(env, "﻿ENVIRONMENT = prod\n")
    run(files)
    assert read(env).count("ENVIRONMENT") == 1


def test_parse_example_collects_comments_and_optional_keys():
    example = sync_env.parse_example(EXAMPLE)
    assert list(example.lines) == ["ENVIRONMENT", "API_PORT", "DB_PASSWORD", "TOKEN_EMPTY"]
    assert example.comments["ENVIRONMENT"] == ["# Cấu hình mẫu", "# Môi trường: dev | prod"]
    assert example.comments["API_PORT"] == ["# Cổng API"]
    assert example.optional == {"OPTIONAL_FLAG"}
    assert sync_env.needs_value(example, list(example.lines)) == ["DB_PASSWORD", "TOKEN_EMPTY"]


def test_append_block_is_dated():
    example = sync_env.parse_example(EXAMPLE)
    text = sync_env.append_missing("A=1", example, ["API_PORT"], date(2026, 11, 8))
    assert (
        text == "A=1\n\n# ---------- Thêm tự động bởi `make env` (2026-11-08) ----------\n# Cổng API\nAPI_PORT=18000\n"
    )


def test_the_real_env_example_is_in_sync_with_itself(tmp_path):
    example = REPO_ROOT / ".env.example"
    env = tmp_path / ".env"
    write(env, read(example))
    before = read(env)
    assert sync_env.main(["--env", str(env), "--example", str(example), "--remove-extra"]) == 0
    assert read(env) == before and not (tmp_path / ".env.bak").exists()
    assert len(sync_env.parse_example(before).lines) > 50


def test_missing_example_file_is_an_error(tmp_path, capsys):
    assert sync_env.main(["--env", str(tmp_path / ".env"), "--example", str(tmp_path / "none")]) == 1
    assert "Không thấy" in capsys.readouterr().err
