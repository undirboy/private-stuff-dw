"""A worked example terminal, modelled on a small Indian domestic departures floor.

Dimensions are plausible rather than surveyed. Replace this module with the real
survey before any trial: everything else in the package reads the map and holds
no assumptions about this particular building.

    kerb ---- checkin ---- sec_q ---- sec_lane
                                          |          <- single-file security lane
                                      sec_exit
                                          |
          g1      g2      g3--lounge  g4      g5     <- gate spurs
           |       |       |           |       |
   sp1 -- sp1 --- sp2 --- sp3 ------- sp4 --- sp5    <- airside spine
    |               |                           |
   sv1 ----------- sv2 ----------------------- sv3   <- service corridor
    |                                           |
  dock_w                                      dock_e
"""

from __future__ import annotations

from .graph import Guide, Node, NodeKind, TerminalMap


def build_example_terminal() -> TerminalMap:
    """The demo map used by the simulator and the tests."""
    tmap = TerminalMap("Example Domestic Terminal")

    landside = [
        Node("kerb", NodeKind.PICKUP, 0, 0, "Forecourt kerbside", tag_id="K01"),
        Node("checkin", NodeKind.JUNCTION, 25, 0, "Check-in row"),
        Node("sec_q", NodeKind.PICKUP, 55, 0, "Security queue head", tag_id="S01"),
        Node("sec_lane", NodeKind.JUNCTION, 65, 0, "Security lane entry"),
        Node("sec_exit", NodeKind.JUNCTION, 65, 18, "Security lane exit"),
    ]

    spine = [
        Node("sp1", NodeKind.JUNCTION, 80, 25, "Spine west"),
        Node("sp2", NodeKind.JUNCTION, 100, 25, "Spine west-central"),
        Node("sp3", NodeKind.JUNCTION, 120, 25, "Spine central"),
        Node("sp4", NodeKind.JUNCTION, 140, 25, "Spine east-central"),
        Node("sp5", NodeKind.JUNCTION, 160, 25, "Spine east"),
    ]

    gates = [
        Node("g1", NodeKind.GATE, 80, 42, "Gate 1", tag_id="G01"),
        Node("g2", NodeKind.GATE, 100, 42, "Gate 2", tag_id="G02"),
        Node("g3", NodeKind.GATE, 120, 42, "Gate 3", tag_id="G03"),
        Node("g4", NodeKind.GATE, 140, 42, "Gate 4", tag_id="G04"),
        Node("g5", NodeKind.GATE, 160, 42, "Gate 5", tag_id="G05"),
        Node("lounge", NodeKind.PICKUP, 120, 58, "Assistance lounge", tag_id="L01"),
    ]

    service = [
        Node("sv1", NodeKind.JUNCTION, 80, 14, "Service corridor west"),
        Node("sv2", NodeKind.JUNCTION, 120, 14, "Service corridor central"),
        Node("sv3", NodeKind.JUNCTION, 160, 14, "Service corridor east"),
        Node("dock_w", NodeKind.DOCK, 70, 8, "Charging dock west", tag_id="D01"),
        Node("dock_e", NodeKind.DOCK, 168, 8, "Charging dock east", tag_id="D02"),
    ]

    for node in landside + spine + gates + service:
        tmap.add(node)

    # Landside: wide public floor, tape under the vinyl, comfortable walking pace.
    tmap.connect("kerb", "checkin", width_m=2.4, max_speed_mps=1.2)
    tmap.connect("checkin", "sec_q", width_m=2.4, max_speed_mps=1.2)
    tmap.connect("sec_q", "sec_lane", width_m=1.8, max_speed_mps=1.0)

    # The security lane. No tape may be laid through the archway, so this stretch
    # runs on sparse tags and dead reckoning, single file, at a crawl. It is the
    # bottleneck of the whole terminal and the segment chairs will queue for.
    tmap.connect(
        "sec_lane",
        "sec_exit",
        width_m=0.9,
        max_speed_mps=0.5,
        guide=Guide.RFID,
        length_m=22.0,  # the lane doglegs around the baggage scanner
    )
    tmap.connect("sec_exit", "sp1", width_m=2.4, max_speed_mps=1.2)

    # Airside spine: the widest, fastest run in the building.
    for a, b in [("sp1", "sp2"), ("sp2", "sp3"), ("sp3", "sp4"), ("sp4", "sp5")]:
        tmap.connect(a, b, width_m=2.8, max_speed_mps=1.4)

    # Gate spurs: single file, slower, because this is where people stand about.
    for spine_node, gate in [
        ("sp1", "g1"),
        ("sp2", "g2"),
        ("sp3", "g3"),
        ("sp4", "g4"),
        ("sp5", "g5"),
    ]:
        tmap.connect(spine_node, gate, width_m=1.2, max_speed_mps=0.9)
    tmap.connect("g3", "lounge", width_m=1.2, max_speed_mps=0.9)

    # Service corridor: back of house, so a painted stripe is good enough. Narrow
    # and single file, which is what makes the deadlock logic worth having.
    tmap.connect("sp1", "sv1", width_m=1.0, max_speed_mps=1.0, guide=Guide.PAINTED)
    tmap.connect("sp3", "sv2", width_m=1.0, max_speed_mps=1.0, guide=Guide.PAINTED)
    tmap.connect("sp5", "sv3", width_m=1.0, max_speed_mps=1.0, guide=Guide.PAINTED)
    tmap.connect("sv1", "sv2", width_m=1.0, max_speed_mps=1.0, guide=Guide.PAINTED)
    tmap.connect("sv2", "sv3", width_m=1.0, max_speed_mps=1.0, guide=Guide.PAINTED)
    tmap.connect("sv1", "dock_w", width_m=1.2, max_speed_mps=0.8, guide=Guide.PAINTED)
    tmap.connect("sv3", "dock_e", width_m=1.2, max_speed_mps=0.8, guide=Guide.PAINTED)

    return tmap
