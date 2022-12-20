# -*- coding: utf-8 -*-
import abc
import enum
import typing as t

import construct_editor.core.entries as entries
from construct_editor.core.callbacks import CallbackListNew
from construct_editor.core.commands import Command, CommandProcessor
from construct_editor.core.preprocessor import add_gui_metadata, get_gui_metadata


class IntegerFormat(enum.Enum):
    Dec = enum.auto()
    Hex = enum.auto()


class ConstructEditorColumn(enum.IntEnum):
    Name = 0
    Type = 1
    Value = 2


class ConstructEditorModel:
    """
    This model acts as a bridge between the DataViewCtrl and the dataclasses.
    This model provides these data columns:
        0. Name: string
        1. Type: string
        2. Value: string
    """

    def __init__(self):
        self.root_entry: t.Optional["entries.EntryConstruct"] = None
        self.root_obj: t.Optional[t.Any] = None

        # Modelwide flag, if hidden entries should be shown (hidden means starting with an underscore)
        self.hide_protected = True

        # Modelwide format of integer values
        self.integer_format = IntegerFormat.Dec

        # List with all entries that have the list view enabled
        self.list_viewed_entries: t.List["entries.EntryConstruct"] = []

        self.command_processor = CommandProcessor(max_commands=20)

    @abc.abstractmethod
    def on_value_changed(self, entry: "entries.EntryConstruct"):
        """Implement this in the derived class"""
        ...

    def get_column_count(self):
        """
        Get the column count.
        """
        return 3

    def get_children(
        self, entry: t.Optional["entries.EntryConstruct"]
    ) -> t.List["entries.EntryConstruct"]:
        """
        Get all children of an entry
        """
        # no root entry set
        if self.root_entry is None:
            return []

        # root entry is requested
        if entry is None:
            self.root_entry.visible_row = True
            return [self.root_entry]

        if entry.subentries is None:
            return []

        children = []
        for subentry in entry.subentries:
            name = subentry.name

            if (self.hide_protected == True) and (name.startswith("_") or name == ""):
                subentry.visible_row = False
                continue

            children.append(subentry)
            subentry.visible_row = True
        return children

    def is_container(self, entry: "entries.EntryConstruct") -> bool:
        """
        Check if an entry is a container (contains children)
        """
        return entry.subentries is not None

    def get_parent(
        self, entry: t.Optional["entries.EntryConstruct"]
    ) -> t.Optional["entries.EntryConstruct"]:
        """
        Get the parent of an entry
        """
        # root entry has no parent
        if entry is None:
            return None

        # get the visible row entry of this entry
        visible_row_entry = entry.get_visible_row_entry()
        if visible_row_entry is None:
            return None

        # get the parent of the visible row entry
        parent = visible_row_entry.parent
        if parent is None:
            return None

        # get the visible row entry of the parent
        return parent.get_visible_row_entry()

    def get_value(self, entry: "entries.EntryConstruct", column: int):
        """
        Return the value to be displayed for this entry in a specific column.
        """
        if column == ConstructEditorColumn.Name:
            return entry.name
        if column == ConstructEditorColumn.Type:
            return entry.typ_str
        if column == ConstructEditorColumn.Value:
            return entry

        # other columns are unused except for list_viewed_entries
        if (entry.parent is None) or (entry.parent not in self.list_viewed_entries):
            return ""

        # flatten the hierarchical structure to a list
        column = column - len(ConstructEditorColumn)
        flat_subentry_list: t.List["entries.EntryConstruct"] = []
        entry.create_flat_subentry_list(flat_subentry_list)
        if len(flat_subentry_list) > column:
            return flat_subentry_list[column].obj_str
        else:
            return ""

    def set_value(
        self, new_value: t.Any, entry: "entries.EntryConstruct", column: int
    ) -> None:
        """
        Set the value of an entry.
        """
        if column != ConstructEditorColumn.Value:
            raise ValueError(f"{column=} cannot be modified")

        # get the current object
        current_value = entry.obj

        # link the metadata from the current object to the new one
        metadata = get_gui_metadata(current_value)
        if metadata is not None:
            new_value = add_gui_metadata(new_value, metadata)

        model = self

        class Cmd(Command):
            def __init__(self) -> None:
                super().__init__(True, f"Value '{entry.path[-1]}' changed")

            def do(self) -> None:
                self._obj_backup = current_value
                entry.obj = new_value
                model.on_value_changed(entry)

            def undo(self) -> None:
                entry.obj = self._obj_backup
                model.on_value_changed(entry)

        self.command_processor.submit(Cmd())
