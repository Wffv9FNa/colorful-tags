# -*- coding: utf-8 -*-

# Colorful Tags for Anki
#
# Copyright (C) 2018-2021  Aristotelis P. <https//glutanimate.com/>
# Copyright (C) 2021  RumovZ <gp5glkw78@relay.firefox.com>
# Coypright (C) 2014  Patrice Neff <http://patrice.ch/>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from typing import TYPE_CHECKING, List

from aqt.browser import SidebarItemType  # type: ignore
from aqt.qt import QAbstractItemView, QColor, QColorDialog, QMenu, QModelIndex

from ..data import user_data
from .item import PatchedSideBarItem

if TYPE_CHECKING:
    from aqt.browser import SidebarTreeView  # type: ignore

# Track which sidebars have been initialized to avoid redundant setup
_initialized_sidebars = set()


def get_selected_tag_items(sidebar: "SidebarTreeView") -> List[PatchedSideBarItem]:
    """Get all selected tag items from sidebar."""
    selected_indexes = sidebar.selectedIndexes()
    items = []

    for index in selected_indexes:
        if index.isValid():
            item: PatchedSideBarItem = index.internalPointer()
            if item.item_type == SidebarItemType.TAG:
                items.append(item)

    return items


def maybe_add_context_actions(
    sidebar: "SidebarTreeView",
    menu: QMenu,
    item: PatchedSideBarItem,
    index: QModelIndex,
):
    # Enable multi-selection on first use (only once per sidebar instance)
    if id(sidebar) not in _initialized_sidebars:
        sidebar.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        sidebar.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        _initialized_sidebars.add(id(sidebar))

    if item.item_type != SidebarItemType.TAG:
        return

    selected_items = get_selected_tag_items(sidebar)

    if not selected_items:
        return

    menu.addSeparator()

    # Single-select mode (existing behavior)
    if len(selected_items) == 1:
        pin_action = "Unpin" if item.is_pinned else "Pin"
        menu.addAction(pin_action, lambda: _toggle_pin(sidebar, item))
        menu.addAction("Assign Color", lambda: _assign_color(sidebar, item))
        if item.color:
            menu.addAction("Remove Color", lambda: _remove_color(sidebar, item))
    # Multi-select mode (new bulk operations)
    else:
        count = len(selected_items)
        pinned_count = sum(1 for item in selected_items if item.is_pinned)
        colored_count = sum(1 for item in selected_items if item.color)

        # Pin/Unpin options
        if pinned_count < count:
            menu.addAction(
                f"Pin Selected ({count} tags)",
                lambda: _bulk_toggle_pin(sidebar, selected_items, True),
            )
        if pinned_count > 0:
            menu.addAction(
                f"Unpin Selected ({count} tags)",
                lambda: _bulk_toggle_pin(sidebar, selected_items, False),
            )

        # Color options
        menu.addAction(
            f"Assign Color to Selected ({count} tags)",
            lambda: _bulk_assign_color(sidebar, selected_items),
        )

        if colored_count > 0:
            menu.addAction(
                f"Remove Color from Selected ({count} tags)",
                lambda: _bulk_remove_color(sidebar, selected_items),
            )


def _toggle_pin(sidebar: "SidebarTreeView", item: PatchedSideBarItem):
    if tag := user_data.tags.get(item.full_name, None):
        if tag.get("pin", False):
            del tag["pin"]
            if not len(tag):
                del user_data.tags[item.full_name]
        else:
            tag["pin"] = True
    else:
        user_data.tags[item.full_name] = {"pin": True}
    user_data.save()
    sidebar.refresh()


def _assign_color(sidebar: "SidebarTreeView", item: PatchedSideBarItem):
    color = QColor(item.color or "#0000FF")
    dialog = QColorDialog(color, parent=sidebar)
    color = dialog.getColor(color)
    if color.isValid():
        if not (tag := user_data.tags.get(item.full_name, None)):
            tag = user_data.tags[item.full_name] = {}  # type: ignore
        tag["color"] = color.name()
        user_data.save()
        sidebar.refresh()


def _remove_color(sidebar: "SidebarTreeView", item: PatchedSideBarItem):
    if tag := user_data.tags.get(item.full_name, None):
        if "color" in tag:
            del tag["color"]
            if not len(tag):
                del user_data.tags[item.full_name]
            user_data.save()
            sidebar.refresh()


def _bulk_assign_color(
    sidebar: "SidebarTreeView", items: List[PatchedSideBarItem]
):
    """Assign a color to multiple tags at once."""
    # Determine preview color (use most common existing color or default blue)
    existing_colors = [item.color for item in items if item.color]
    preview_color = existing_colors[0] if existing_colors else "#0000FF"

    color = QColor(preview_color)
    dialog = QColorDialog(color, parent=sidebar)
    dialog.setWindowTitle(f"Assign Color to {len(items)} Tags")
    color = dialog.getColor(color)

    if color.isValid():
        # Batch update all tags
        for item in items:
            if not (tag := user_data.tags.get(item.full_name, None)):
                tag = user_data.tags[item.full_name] = {}  # type: ignore
            tag["color"] = color.name()

        # Single save and refresh
        user_data.save()
        sidebar.refresh()


def _bulk_remove_color(
    sidebar: "SidebarTreeView", items: List[PatchedSideBarItem]
):
    """Remove color from multiple tags at once."""
    changed = False
    for item in items:
        if tag := user_data.tags.get(item.full_name, None):
            if "color" in tag:
                del tag["color"]
                if not len(tag):
                    del user_data.tags[item.full_name]
                changed = True

    if changed:
        user_data.save()
        sidebar.refresh()


def _bulk_toggle_pin(
    sidebar: "SidebarTreeView", items: List[PatchedSideBarItem], pin_state: bool
):
    """Pin or unpin multiple tags at once."""
    for item in items:
        if pin_state:
            # Pin the tag
            if tag := user_data.tags.get(item.full_name, None):
                tag["pin"] = True
            else:
                user_data.tags[item.full_name] = {"pin": True}
        else:
            # Unpin the tag
            if tag := user_data.tags.get(item.full_name, None):
                if tag.get("pin", False):
                    del tag["pin"]
                    if not len(tag):
                        del user_data.tags[item.full_name]

    user_data.save()
    sidebar.refresh()
