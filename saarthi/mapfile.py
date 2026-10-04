"""The terminal map as a plain file the airport owns.

A guide path is not a fixed thing. Terminals get reconfigured, gates get
renumbered, a pier closes for works, a retail unit moves and the line round it
has to move too. If every one of those changes means raising a ticket with the
supplier and waiting, the system becomes a thing the airport is stuck with rather
than a thing it runs.

So the map is readable JSON with no vendor-specific encoding. An airport's own
facilities team can open it, change a speed limit, add a gate or close a corridor
with a text editor, validate it, and put it back — without this repository and
without us.

    python3 -m saarthi.mapfile terminal.json --validate

This is a procurement argument as much as a technical one. "Who owns the map, and
what does it cost us to change it" is a question that gets asked in a tender, and
most answers to it are bad.
"""

from __future__ import annotations

import json
import pathlib
import sys

from .graph import Guide, Node, NodeKind, TerminalMap

#: Bumped when the on-disk shape changes in a way older files would not survive.
FORMAT_VERSION = 1


class MapFileError(ValueError):
    """The file is not a terminal map we can load."""


def to_dict(tmap: TerminalMap) -> dict:
    """The map as plain data: dicts, lists, strings and numbers."""
    return {
        "format": "saarthi.terminal-map",
        "version": FORMAT_VERSION,
        "name": tmap.name,
        "nodes": [
            {
                "id": node.id,
                "kind": node.kind.value,
                "x": round(node.x, 3),
                "y": round(node.y, 3),
                "label": node.label,
                "tag": node.tag_id,
            }
            for node in tmap.nodes.values()
        ],
        "segments": [
            {
                "a": segment.a,
                "b": segment.b,
                "length_m": round(segment.length_m, 3),
                "max_speed_mps": segment.max_speed_mps,
                "width_m": segment.width_m,
                "guide": segment.guide.value,
            }
            for segment in tmap.segments.values()
        ],
    }


def dumps(tmap: TerminalMap) -> str:
    """Serialise, formatted to be read and diffed by a person."""
    return json.dumps(to_dict(tmap), indent=2, ensure_ascii=False) + "\n"


def _require(mapping: dict, key: str, where: str):
    if key not in mapping:
        raise MapFileError(f"{where} has no {key!r}")
    return mapping[key]


def from_dict(data: dict) -> TerminalMap:
    """Rebuild a map from plain data, saying precisely what is wrong if it is.

    The error messages matter more than usual here: the person editing this file
    is a facilities engineer with a text editor, not a Python programmer, and
    "KeyError: 'kind'" tells them nothing they can act on.
    """
    if not isinstance(data, dict):
        raise MapFileError("a terminal map file must contain a JSON object")

    version = data.get("version")
    if version is None:
        raise MapFileError("file has no 'version'; is it a terminal map?")
    if version > FORMAT_VERSION:
        raise MapFileError(
            f"file is version {version}, this software reads up to {FORMAT_VERSION}"
        )

    tmap = TerminalMap(data.get("name", "unnamed terminal"))

    nodes = _require(data, "nodes", "file")
    if not isinstance(nodes, list):
        raise MapFileError("'nodes' must be a list")

    for index, entry in enumerate(nodes):
        where = f"node {index}"
        node_id = _require(entry, "id", where)
        kind_name = _require(entry, "kind", f"node {node_id!r}")
        try:
            kind = NodeKind(kind_name)
        except ValueError:
            valid = ", ".join(k.value for k in NodeKind)
            raise MapFileError(
                f"node {node_id!r} has kind {kind_name!r}; expected one of: {valid}"
            ) from None
        try:
            tmap.add(
                Node(
                    id=node_id,
                    kind=kind,
                    x=float(_require(entry, "x", f"node {node_id!r}")),
                    y=float(_require(entry, "y", f"node {node_id!r}")),
                    label=entry.get("label", ""),
                    tag_id=entry.get("tag"),
                )
            )
        except (TypeError, ValueError) as exc:
            raise MapFileError(f"node {node_id!r}: {exc}") from exc

    segments = _require(data, "segments", "file")
    if not isinstance(segments, list):
        raise MapFileError("'segments' must be a list")

    for index, entry in enumerate(segments):
        where = f"segment {index}"
        a = _require(entry, "a", where)
        b = _require(entry, "b", where)
        guide_name = entry.get("guide", Guide.MAGNETIC.value)
        try:
            guide = Guide(guide_name)
        except ValueError:
            valid = ", ".join(g.value for g in Guide)
            raise MapFileError(
                f"segment {a}-{b} has guide {guide_name!r}; expected one of: {valid}"
            ) from None
        try:
            tmap.connect(
                a,
                b,
                length_m=entry.get("length_m"),
                max_speed_mps=float(entry.get("max_speed_mps", 1.2)),
                width_m=float(entry.get("width_m", 1.8)),
                guide=guide,
            )
        except ValueError as exc:
            raise MapFileError(f"segment {a}-{b}: {exc}") from exc

    return tmap


def loads(text: str) -> TerminalMap:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MapFileError(f"not valid JSON: line {exc.lineno}, column {exc.colno}") from exc
    return from_dict(data)


def save_map(tmap: TerminalMap, path: str | pathlib.Path) -> pathlib.Path:
    out = pathlib.Path(path)
    out.write_text(dumps(tmap), encoding="utf-8")
    return out


def load_map(path: str | pathlib.Path) -> TerminalMap:
    return loads(pathlib.Path(path).read_text(encoding="utf-8"))


#: Short aliases, for use when the module is imported by name.
save = save_map
load = load_map


def main(argv: list[str] | None = None) -> int:
    """``python3 -m saarthi.mapfile <file.json> [--validate]``

    Gives the facilities team a way to check a map they have edited without
    writing any code: it loads the file, reports anything wrong in plain words,
    and prints what it found.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(__doc__.strip().splitlines()[0])
        print("usage: python3 -m saarthi.mapfile <file.json> [--validate]")
        return 2

    path = args[0]
    try:
        tmap = load(path)
    except (MapFileError, OSError) as exc:
        print(f"{path}: {exc}")
        return 1

    print(f"{tmap.name}: {len(tmap.nodes)} nodes, {len(tmap.segments)} segments")

    if "--validate" in args:
        problems = tmap.validate()
        if problems:
            print(f"\n{len(problems)} problem(s):")
            for problem in problems:
                print(f"  ! {problem}")
            return 1
        print("map is valid: every gate reachable, every stop tagged")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
