"""Preflight catalog ảnh lúc khởi động: thiếu file thì cảnh báo rõ một lần, ảnh tắt, chat text vẫn chạy."""

import logging

from app.services import answer_media, image_cache, images
from app.services.images import ImageCatalog
from core.config import Settings


def catalog(tmp_path, *, enabled=True, create=()):
    for name in create:
        (tmp_path / name).write_text("x", encoding="utf-8")
    return ImageCatalog(
        Settings(
            _env_file=None,
            rag_images_enabled=enabled,
            rag_images_catalog=str(tmp_path / "images.csv"),
            rag_images_documents=str(tmp_path / "docs.jsonl"),
        )
    )


def test_default_catalog_points_to_delivery_release():
    assert Settings(_env_file=None).rag_images_catalog == "data/delivery/final/clean/images.csv"


def test_missing_catalog_logs_one_warning_with_configured_path(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="app.services.images"):
        assert catalog(tmp_path, create=["docs.jsonl"]).preflight() is False
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert str(tmp_path / "images.csv") in warnings[0].getMessage()


def test_missing_documents_also_warns_once(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="app.services.images"):
        assert catalog(tmp_path, create=["images.csv"]).preflight() is False
    assert [str(tmp_path / "docs.jsonl") in r.getMessage() for r in caplog.records] == [True]


def test_present_catalog_and_disabled_images_are_silent(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="app.services.images"):
        assert catalog(tmp_path, create=["images.csv", "docs.jsonl"]).preflight() is True
        assert catalog(tmp_path, enabled=False).preflight() is True
    assert caplog.records == []


async def test_unavailable_catalog_keeps_images_off(tmp_path):
    result = await catalog(tmp_path).resolve([], [])
    assert result.images == [] and result.reasons == {"catalog_unavailable": 1}


def test_image_services_share_cache_module_without_import_cycle():
    assert images.CACHE is image_cache.CACHE and answer_media.CACHE is image_cache.CACHE
    assert images.FORMATS is image_cache.FORMATS and answer_media.FORMATS is image_cache.FORMATS
