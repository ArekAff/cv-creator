"""YAML helpers: UTF-8, key order preserved, multi-line strings written as blocks."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class YamlError(Exception):
    pass


class _Dumper(yaml.SafeDumper):
    pass


def _represent_str(dumper: yaml.SafeDumper, data: str) -> yaml.Node:
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_Dumper.add_representer(str, _represent_str)


def load(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
        problem = getattr(exc, "problem", None) or str(exc)
        raise YamlError(f"{path}: invalid YAML{where}: {problem}") from None
    return default if data is None else data


def dump(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.dump(data, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=100)
    path.write_text(text, encoding="utf-8")
