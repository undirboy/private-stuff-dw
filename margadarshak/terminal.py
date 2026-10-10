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

from .graph import Guide, Lift, Node, NodeKind, TerminalMap, Zone


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
        Node("g1", NodeKind.GATE, 80, 42, "Gate 1", tag_id="G01",
             code="1", terminal="1"),
        Node("g2", NodeKind.GATE, 100, 42, "Gate 2", tag_id="G02",
             code="2", terminal="1"),
        Node("g3", NodeKind.GATE, 120, 42, "Gate 3", tag_id="G03",
             code="3", terminal="1"),
        Node("g4", NodeKind.GATE, 140, 42, "Gate 4", tag_id="G04",
             code="4", terminal="1"),
        Node("g5", NodeKind.GATE, 160, 42, "Gate 5", tag_id="G05",
             code="5", terminal="1"),
        Node("lounge", NodeKind.PICKUP, 120, 58, "Assistance lounge", tag_id="L01",
             terminal="1"),
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


def build_two_level_terminal() -> TerminalMap:
    """The same terminal with departures upstairs, which is the usual arrangement.

    Dabolim and Mopa both put the road, check-in and security on one level and
    the gates on another. A flat map cannot describe that journey at all, and a
    flat map is the one thing a demonstration is always tempted to settle for,
    because every hard case in a building is a change of level.

    What this map is for is the decisions that only exist once there is an
    upstairs: whether a gate two lifts away is really nearer than one along the
    pier, what happens to a queue of chairs when a single car is the only way up,
    and whether a chair that comes out of a lift knows which floor it is on.

        level 1   lb_w1 -- sp1 -- sp2 -- sp3 -- sp4 -- sp5 -- lb_e1
                              |      |      |      |      |      |
                             g1     g2     g3     g4     g5   dock_e
                                           |
                                        lounge

        level 0   lb_w0 ------------------------------------- lb_e0
                     |  \\                                       |
                   sv1 -- dock_w                            sec_exit
                                                                 |
                              kerb -- checkin -- sec_q -- sec_lane

    Two lifts, deliberately. One lift to a level with gates on it is a single
    point of failure that strands exactly the people who cannot take the stairs,
    and :meth:`TerminalMap.validate` says so about any survey that tries it.

    Security is the other thing this map gets right and the flat one does not.
    The archway is a :class:`~margadarshak.graph.Zone` boundary and nothing drives
    across it, so this is two fleets: landside chairs working the kerb and the
    queue, airside chairs working the lifts and the piers. A kerb-to-gate journey
    is therefore two journeys with the screening hall in between, which is what
    it is in the building.
    """
    tmap = TerminalMap("Example Two-Level Terminal")

    # -- landside, level 0: road, check-in, the queue for security ----------
    for node in [
        Node("kerb", NodeKind.PICKUP, 0, 0, "Forecourt kerbside", tag_id="K01"),
        Node("checkin", NodeKind.JUNCTION, 25, 0, "Check-in row"),
        Node("dock_l", NodeKind.DOCK, 20, 10, "Charging dock, landside", tag_id="D00"),
        Node("sec_q", NodeKind.PICKUP, 55, 0, "Security queue head", tag_id="S01"),
        #: Where the landside journey ends. The passenger gets out here, is
        #: screened on foot, and the chair goes no further.
        Node("sec_lane", NodeKind.PICKUP, 65, 0, "Security, landside",
             tag_id="S02"),
    ]:
        tmap.add(node)

    # -- airside, level 0: out of screening, and the lift lobbies -----------
    for node in [
        Node("sec_exit", NodeKind.PICKUP, 65, 18, "Security, airside",
             tag_id="S03", zone=Zone.AIRSIDE),
        Node("lb_w0", NodeKind.LIFT, 80, 25, "West lift, ground",
             tag_id="LW0", zone=Zone.AIRSIDE),
        Node("lb_e0", NodeKind.LIFT, 160, 25, "East lift, ground",
             tag_id="LE0", zone=Zone.AIRSIDE),
        Node("sv1", NodeKind.JUNCTION, 80, 14, "Service corridor",
             zone=Zone.AIRSIDE),
        Node("dock_w", NodeKind.DOCK, 70, 8, "Charging dock, airside ground",
             tag_id="D01", zone=Zone.AIRSIDE),
    ]:
        tmap.add(node)

    # -- level 1: departures ------------------------------------------------
    for node in [
        Node("lb_w1", NodeKind.LIFT, 80, 25, "West lift, departures",
             tag_id="LW1", level=1, zone=Zone.AIRSIDE),
        Node("lb_e1", NodeKind.LIFT, 160, 25, "East lift, departures",
             tag_id="LE1", level=1, zone=Zone.AIRSIDE),
        Node("sp1", NodeKind.JUNCTION, 84, 25, "Spine west", level=1, zone=Zone.AIRSIDE),
        Node("sp2", NodeKind.JUNCTION, 100, 25, "Spine west-central", level=1, zone=Zone.AIRSIDE),
        Node("sp3", NodeKind.JUNCTION, 120, 25, "Spine central", level=1, zone=Zone.AIRSIDE),
        Node("sp4", NodeKind.JUNCTION, 140, 25, "Spine east-central", level=1, zone=Zone.AIRSIDE),
        Node("sp5", NodeKind.JUNCTION, 156, 25, "Spine east", level=1, zone=Zone.AIRSIDE),
        Node("g1", NodeKind.GATE, 84, 42, "Gate 1", tag_id="G01",
             code="1", terminal="1", level=1, zone=Zone.AIRSIDE),
        Node("g2", NodeKind.GATE, 100, 42, "Gate 2", tag_id="G02",
             code="2", terminal="1", level=1, zone=Zone.AIRSIDE),
        Node("g3", NodeKind.GATE, 120, 42, "Gate 3", tag_id="G03",
             code="3", terminal="1", level=1, zone=Zone.AIRSIDE),
        Node("g4", NodeKind.GATE, 140, 42, "Gate 4", tag_id="G04",
             code="4", terminal="1", level=1, zone=Zone.AIRSIDE),
        Node("g5", NodeKind.GATE, 156, 42, "Gate 5", tag_id="G05",
             code="5", terminal="1", level=1, zone=Zone.AIRSIDE),
        Node("lounge", NodeKind.PICKUP, 120, 58, "Assistance lounge",
             tag_id="L01", terminal="1", level=1, zone=Zone.AIRSIDE),
        Node("dock_e", NodeKind.DOCK, 164, 18, "Charging dock, departures",
             tag_id="D02", level=1, zone=Zone.AIRSIDE),
    ]:
        tmap.add(node)

    # Landside floor: kerb, check-in, the dock, the queue.
    tmap.connect("kerb", "checkin", width_m=2.4, max_speed_mps=1.2)
    tmap.connect("checkin", "dock_l", width_m=1.6, max_speed_mps=1.0)
    tmap.connect("checkin", "sec_q", width_m=2.4, max_speed_mps=1.2)
    tmap.connect("sec_q", "sec_lane", width_m=1.8, max_speed_mps=1.0)

    # Security. The passenger walks or is pushed through the metal detector; the
    # chair is inspected and swabbed if it goes at all, and it does not. This
    # edge exists so that the map knows the two zones are two ends of one
    # journey — no route is ever planned across it.
    tmap.connect("sec_lane", "sec_exit", width_m=1.2, length_m=22.0, screening=True)

    # The landside concourse, joining the security exit to both lift lobbies.
    # Both, so that which lift to take is a real decision rather than a detail of
    # how the map was drawn: the west car is nearer and the east car is slower to
    # answer, and the planner should be the thing that works out when each wins.
    tmap.connect("sec_exit", "lb_w0", width_m=2.4, max_speed_mps=1.2)
    tmap.connect("sec_exit", "lb_e0", width_m=2.4, max_speed_mps=1.2)
    tmap.connect("lb_w0", "lb_e0", width_m=2.4, max_speed_mps=1.2)
    tmap.connect("lb_w0", "sv1", width_m=1.0, max_speed_mps=1.0, guide=Guide.PAINTED)
    tmap.connect("sv1", "dock_w", width_m=1.2, max_speed_mps=0.8, guide=Guide.PAINTED)

    # The two lifts. Slow, exclusive, and the only way between the levels.
    tmap.connect("lb_w0", "lb_w1", lift=Lift("lift_w"))
    tmap.connect("lb_e0", "lb_e1", lift=Lift("lift_e", call_s=35.0))

    # Departures: spine, gate spurs, lounge, airside charging bay.
    tmap.connect("lb_w1", "sp1", width_m=2.8, max_speed_mps=1.2)
    tmap.connect("sp5", "lb_e1", width_m=2.8, max_speed_mps=1.2)
    for a, b in [("sp1", "sp2"), ("sp2", "sp3"), ("sp3", "sp4"), ("sp4", "sp5")]:
        tmap.connect(a, b, width_m=2.8, max_speed_mps=1.4)
    for spine_node, gate in [
        ("sp1", "g1"),
        ("sp2", "g2"),
        ("sp3", "g3"),
        ("sp4", "g4"),
        ("sp5", "g5"),
    ]:
        tmap.connect(spine_node, gate, width_m=1.2, max_speed_mps=0.9)
    tmap.connect("g3", "lounge", width_m=1.2, max_speed_mps=0.9)
    tmap.connect("sp5", "dock_e", width_m=1.2, max_speed_mps=0.8, guide=Guide.PAINTED)

    return tmap
