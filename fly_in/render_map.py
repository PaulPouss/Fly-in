import math

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.colors import is_color_like
from matplotlib.patches import FancyArrow

from .classes import BlockedHub, Hub, HubRole, MapInfo, PriorityHub
from .classes import RestrictedHub

# Fallback background color per zone type, used only when the file
# does not provide a color= metadata for that hub.
_DEFAULT_COLOR_BY_TYPE: dict[type, str] = {
    BlockedHub: "dimgray",
    RestrictedHub: "lightcoral",
    PriorityHub: "khaki",
}

# Marker shape per role, so start/end stand out regardless of color.
_MARKER_BY_ROLE: dict[HubRole, str] = {
    HubRole.START: "s",   # square
    HubRole.END: "*",     # star
    HubRole.NORMAL: "o",  # circle
}

_INCHES_PER_UNIT = 0.7
_MIN_FIG_SIZE = 6.0
_MAX_FIG_SIZE = 40.0


class RenderMap():
    def __init__(self, map_info: MapInfo) -> None:
        self.map_info: MapInfo = map_info

    def _hub_color(self, hub: Hub) -> str:
        if hub.color is not None and is_color_like(hub.color):
            return hub.color
        return _DEFAULT_COLOR_BY_TYPE.get(type(hub), "lightsteelblue")

    def _hub_marker(self, hub: Hub) -> str:
        return _MARKER_BY_ROLE[hub.role]

    def _nearest_neighbor_gap(self) -> float:
        """Smallest distance between any two hubs, used to scale marker
        and font size so they don't overlap on dense maps. Falls back
        to 1.0 if there is only one hub or several share coordinates.
        """
        hubs = self.map_info.hub_list
        min_gap = math.inf
        for i, a in enumerate(hubs):
            for b in hubs[i + 1:]:
                dist = math.hypot(a.x - b.x, a.y - b.y)
                if 0 < dist < min_gap:
                    min_gap = dist
        return min_gap if min_gap != math.inf else 1.0

    def render(self, output_path: str,
               drone_positions: dict[str, int] | None = None,
               transit_positions: dict[str, int] | None = None,
               title: str | None = None) -> None:
        """Draw the map (zones, connections, capacities) and save it to
        output_path.

        drone_positions, if given, maps a hub name to the number of
        drones currently sitting on it.
        transit_positions, if given, maps a connection name to the
        number of drones currently in forced transit on it (toward a
        restricted zone), drawn at the connection's midpoint.

        Marker size, font size and figure size are scaled from the
        smallest distance between two hubs, so dense maps (many hubs
        close together) automatically get smaller markers/labels
        instead of overlapping.
        """
        hubs = self.map_info.hub_list
        xs = [hub.x for hub in hubs]
        ys = [hub.y for hub in hubs]
        extent_x = max(xs) - min(xs) if hubs else 0
        extent_y = max(ys) - min(ys) if hubs else 0
        gap = self._nearest_neighbor_gap()

        fig_w = min(max(extent_x * _INCHES_PER_UNIT + 3, _MIN_FIG_SIZE),
                    _MAX_FIG_SIZE)
        fig_h = min(max(extent_y * _INCHES_PER_UNIT + 3, _MIN_FIG_SIZE),
                    _MAX_FIG_SIZE)

        fig, ax = plt.subplots(figsize=(fig_w, fig_h))

        # Marker diameter targets ~55% of the smallest gap between two
        # hubs, converted from data units to points via the figure's
        # inches-per-unit scale.
        diameter_in = min(gap * _INCHES_PER_UNIT * 0.55, 0.5)
        diameter_pt = diameter_in * 72
        marker_size = diameter_pt ** 2
        font_size = max(min(diameter_pt * 0.28, 9), 5)

        self._draw_connections(ax, font_size)
        self._draw_hubs(ax, drone_positions, marker_size, font_size,
                        diameter_pt)
        if transit_positions:
            self._draw_transit(ax, transit_positions, marker_size,
                               font_size)

        ax.set_aspect("equal")
        ax.autoscale()
        ax.margins(0.15)
        # Reserve room above the topmost label for the title (see
        # above) and a smaller margin below the lowest marker, since a
        # hub whose label is placed above it has nothing drawn below
        # its marker -- without this, bbox_inches="tight" would crop
        # right at the marker's edge with no breathing room.
        title_clearance_pt = diameter_pt / 2 + 4 + font_size + 22
        title_clearance_units = (
            title_clearance_pt / 72 / _INCHES_PER_UNIT
        )
        bottom_clearance_units = (
            (diameter_pt / 2 + 6) / 72 / _INCHES_PER_UNIT
        )
        y0, y1 = ax.get_ylim()
        ax.set_ylim(y0 - bottom_clearance_units,
                    y1 + title_clearance_units)
        x_clearance_units = (
            (diameter_pt / 2 + 6) / 72 / _INCHES_PER_UNIT
        )
        x0, x1 = ax.get_xlim()
        ax.set_xlim(x0 - x_clearance_units, x1 + x_clearance_units)
        ax.axis("off")
        ax.set_title(title if title is not None else "Fly-in map")
        # bbox_inches="tight" re-measures everything actually drawn
        # (markers, labels, title, legend) and expands the saved
        # canvas to fit it exactly. A fixed-percentage margin
        # (ax.margins alone) is a fraction of the *data* range, which
        # is not enough physical space on maps with a small coordinate
        # extent (e.g. a single row of hubs): markers/labels would
        # otherwise get clipped by the figure edge.
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

    def _label_above(self, hub: Hub, others: list[Hub]) -> bool:
        """Decide whether this hub's label should be placed above or
        below its marker. Chosen to point away from the nearest other
        hub (in y), so two vertically-stacked neighbors don't have
        their labels pushed toward each other. Falls back to True
        (above) when there is no other hub or the nearest one is at
        the same y (no vertical conflict to avoid)."""
        nearest: Hub | None = None
        nearest_dist = math.inf
        for other in others:
            if other is hub:
                continue
            dist = math.hypot(other.x - hub.x, other.y - hub.y)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = other
        if nearest is None or nearest.y == hub.y:
            return True
        # Nearest neighbor is above -> put the label below, and vice
        # versa, so the two labels are pushed apart from each other.
        return nearest.y < hub.y

    def _draw_transit(self, ax: Axes,
                      transit_positions: dict[str, int],
                      marker_size: float, font_size: float) -> None:
        connections_by_name = {
            c.name: c for c in self.map_info.connection_list
        }
        for connection_name, drone_count in transit_positions.items():
            connection = connections_by_name.get(connection_name)
            if connection is None:
                continue
            a, b = connection.first_hub, connection.second_hub
            mid_x = (a.x + b.x) / 2
            mid_y = (a.y + b.y) / 2
            ax.scatter(
                mid_x, mid_y,
                s=marker_size * 0.5, marker="^",
                c="orange", edgecolors="black", linewidths=1.0,
                zorder=3,
            )
            ax.annotate(
                f"{drone_count} in transit",
                (mid_x, mid_y),
                textcoords="offset points", xytext=(0, 10),
                fontsize=font_size, ha="center", va="bottom",
                color="darkorange",
            )

    def _draw_connections(self, ax: Axes, font_size: float) -> None:
        for connection in self.map_info.connection_list:
            a, b = connection.first_hub, connection.second_hub
            ax.plot(
                [a.x, b.x], [a.y, b.y],
                color="black", linewidth=1.0, zorder=1,
            )
            if connection.max_link_capacity > 1:
                mid_x = (a.x + b.x) / 2
                mid_y = (a.y + b.y) / 2
                ax.annotate(
                    f"x{connection.max_link_capacity}",
                    (mid_x, mid_y),
                    fontsize=max(font_size - 1, 4), color="dimgray",
                    ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.1",
                              facecolor="white", edgecolor="none",
                              alpha=0.8),
                )

    def _draw_hubs(self, ax: Axes,
                   drone_positions: dict[str, int] | None,
                   marker_size: float, font_size: float,
                   diameter_pt: float) -> None:
        # Label placement points away from each hub's nearest
        # neighbor, so two hubs close together (e.g. stacked
        # vertically one unit apart) don't push their labels toward
        # each other into the same cramped space.
        hubs = self.map_info.hub_list
        for hub in hubs:
            ax.scatter(
                hub.x, hub.y,
                s=marker_size, marker=self._hub_marker(hub),
                c=self._hub_color(hub),
                edgecolors="black", linewidths=1.0, zorder=2,
            )
            label = hub.name
            if drone_positions and drone_positions.get(hub.name):
                label += f"\n({drone_positions[hub.name]})"

            offset_y = diameter_pt / 2 + 4
            above = self._label_above(hub, hubs)
            ax.annotate(
                label, (hub.x, hub.y),
                textcoords="offset points",
                xytext=(0, offset_y if above else -offset_y),
                fontsize=font_size,
                ha="center", va="bottom" if above else "top",
            )

        self._draw_legend(ax)

    def _draw_legend(self, ax: Axes) -> None:
        handles = [
            FancyArrow(
                0, 0, 0, 0, facecolor=color, edgecolor="black",
                label=label,
            )
            for color, label in [
                ("lightsteelblue", "normal"),
                ("khaki", "priority"),
                ("lightcoral", "restricted"),
                ("dimgray", "blocked"),
            ]
        ]
        ax.legend(
            handles=handles, loc="upper left",
            bbox_to_anchor=(1.02, 1), fontsize=8,
            title="Zone type (fallback color)",
        )
