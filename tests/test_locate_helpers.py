import importlib.util
import sys
import types
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = PLUGIN_ROOT / "main.py"


def _load_module():
    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    api.logger = types.SimpleNamespace()
    api.event = types.SimpleNamespace(AstrMessageEvent=object, filter=types.SimpleNamespace())
    api.message_components = types.SimpleNamespace(At=object, Image=object, Plain=object, Reply=object)
    api.star = types.SimpleNamespace(Context=object, Star=object, register=lambda *args: (lambda cls: cls))
    astrbot.api = api
    sys.modules.update({
        "astrbot": astrbot,
        "astrbot.api": api,
        "astrbot.api.event": api.event,
        "astrbot.api.message_components": api.message_components,
        "astrbot.api.star": api.star,
    })
    api.event.filter.EventMessageType = types.SimpleNamespace(ALL=object())
    api.event.filter.event_message_type = lambda *_args, **_kwargs: (lambda fn: fn)

    spec = importlib.util.spec_from_file_location("kktools_test_module", MAIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


kktools = _load_module()


def test_parse_search_block_accepts_chinese_boolean_and_numbered_queries():
    text = """NEED_SEARCH：是
SEARCH_QUERIES:
1. 独特建筑名称
2、清晰路牌文字
🏆 第一可能位置：...
"""

    assert kktools.KKTools._parse_locate_search_block(text) == (
        True,
        ["独特建筑名称", "清晰路牌文字"],
    )


def test_parse_search_block_drops_queries_when_search_is_disabled():
    text = "NEED_SEARCH: no\nSEARCH_QUERIES:\n- 某个地点\n🏆 第一可能位置：..."

    assert kktools.KKTools._parse_locate_search_block(text) == (False, [])


def test_clean_search_query_normalizes_and_limits_input():
    assert kktools.KKTools._clean_search_query("  独特\n地标  ") == "独特 地标"
    assert kktools.KKTools._clean_search_query("none") == ""
    assert kktools.KKTools._clean_search_query("a") == ""
    assert len(kktools.KKTools._clean_search_query("x" * 200)) == 120


def test_sanitize_search_text_removes_controls_and_limits_size():
    result = kktools.KKTools._sanitize_search_text("标题\n\x00正文")

    assert result == "标题 正文"
    assert len(kktools.KKTools._sanitize_search_text("x" * 2000)) == 1800


def test_strip_locate_search_block_keeps_candidate_output():
    text = "视觉线索\nNEED_SEARCH: yes\nSEARCH_QUERIES:\n- 地标\n🏆 第一可能位置：A"

    result = kktools.KKTools._strip_locate_search_block(text)

    assert "NEED_SEARCH" not in result
    assert "SEARCH_QUERIES" not in result
    assert "🏆 第一可能位置：A" in result
