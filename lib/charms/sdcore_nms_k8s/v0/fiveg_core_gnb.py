"""TODO: Add a proper docstring here.

This is a placeholder docstring for this charm library. Docstrings are
presented on Charmhub and updated whenever you push a new version of the
library.

Complete documentation about creating and documenting libraries can be found
in the SDK docs at https://juju.is/docs/sdk/libraries.

See `charmcraft publish-lib` and `charmcraft fetch-lib` for details of how to
share and consume charm libraries. They serve to enhance collaboration
between charmers. Use a charmer's libraries for classes that handle
integration with their charm.

Bear in mind that new revisions of the different major API versions (v0, v1,
v2 etc) are maintained independently.  You can continue to update v0 and v1
after you have pushed v3.

Markdown is supported, following the CommonMark specification.
"""

import json
import logging
from dataclasses import dataclass

from interface_tester.schema_base import DataBagSchema
from ops.charm import CharmBase, CharmEvents, RelationChangedEvent, RelationJoinedEvent
from ops.framework import EventBase, EventSource, Handle, Object
from pydantic import BaseModel, Field, ValidationError

# The unique Charmhub library identifier, never change it
LIBID = "196ff8f539ba4f2998209fbb50e2dbbf"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1

logger = logging.getLogger(__name__)

"""Schemas definition for the provider and requirer sides of the `fiveg_core_gnb` interface.
It exposes two interfaces.schema_base.DataBagSchema subclasses called:
- ProviderSchema
- RequirerSchema

Examples:
    ProviderSchema:
        unit: <empty>
        app: {
            "tac": 1,
            "plmns": [
                {
                    "mcc": "001",
                    "mnc": "01",
                    "sst": 1,
                    "sd": 1,
                }
            ],
        }
    RequirerSchema:
        unit: <empty>
        app: {
            "cu_id": "gnb001",
        }
"""


@dataclass
class PLMNConfig:
    """Dataclass representing the configuration for a PLMN."""

    mcc: str
    mnc: str
    sst: int
    sd: int


class FivegCoreGnbProviderAppData(BaseModel):
    tac: int = Field(
        description="Tracking Area Code",
        examples=[1],
        ge=1,
        le=16777215,
    )
    plmn: list[PLMNConfig]


class ProviderSchema(DataBagSchema):
    """Provider schema for fiveg_core_gnb."""

    app_data: FivegCoreGnbProviderAppData


def data_matches_provider_schema(data: dict) -> bool:
    """Return whether data matches provider schema.

    Args:
        data (dict): Data to be validated.

    Returns:
        bool: True if data matches provider schema, False otherwise.
    """
    try:
        ProviderSchema(app_data=FivegCoreGnbProviderAppData(**data))
        return True
    except ValidationError as e:
        logger.error("Invalid data: %s", e)
        return False


class FivegCoreGnbRequestEvent(EventBase):
    """Dataclass for the `fiveg_core_gnb` request event."""

    def __init__(self, handle: Handle, relation_id: int):
        """Set relation id.

        Args:
            handle (Handle): Juju framework handle.
            relation_id : ID of the relation.
        """
        super().__init__(handle)
        self.relation_id = relation_id

    def snapshot(self) -> dict:
        """Return event data.

        Returns:
            (dict): contains the relation ID.
        """
        return {
            "relation_id": self.relation_id,
        }

    def restore(self, snapshot: dict) -> None:
        """Restore event data.

        Args:
            snapshot (dict): contains the relation ID.
        """
        self.relation_id = snapshot["relation_id"]


class FivegCoreGnbProviderCharmEvents(CharmEvents):
    """Custom events for the FivegCoreGnbProvider."""

    fiveg_core_gnb_request = EventSource(FivegCoreGnbRequestEvent)


class FivegCoreGnbProvides(Object):
    """Class to be instantiated by provider of the `fiveg_core_gnb`."""

    on = GnbIdentityProviderCharmEvents()  # type: ignore

    def __init__(self, charm: CharmBase, relation_name: str):
        """Observe relation joined event.

        Args:
            charm: Juju charm
            relation_name (str): Relation name
        """
        self.relation_name = relation_name
        self.charm = charm
        super().__init__(charm, relation_name)
        self.framework.observe(charm.on[relation_name].relation_joined, self._on_relation_joined)

    def publish_fiveg_core_gnb_information(
            self, relation_id: int, tac: int, plmns: list[PLMNConfig]
    ) -> None:
        """Set TAC and PLMNs in the relation data.

        Args:
            relation_id (str): Relation ID.
            tac (int): Tracking Area Code.
            plmns (list[PLMNConfig]): Configured PLMNs.
        """
        if not data_matches_provider_schema(
                data={"tac": tac, "plmns": plmns}
        ):
            raise ValueError(f"Invalid fiveG core gNB data: {tac}, {plmns}")
        relation = self.model.get_relation(
            relation_name=self.relation_name, relation_id=relation_id
        )
        if not relation:
            raise RuntimeError(f"Relation {self.relation_name} not created yet.")
        relation.data[self.charm.app]["tac"] = str(tac)
        relation.data[self.charm.app].update({"plmns": json.dumps(plmns)})

    def _on_relation_joined(self, event: RelationJoinedEvent) -> None:
        """Triggered whenever a requirer charm joins the relation.

        Args:
            event (RelationJoinedEvent): Juju event
        """
        self.on.fiveg_core_gnb_request.emit(relation_id=event.relation.id)


class FivegCoreGnbAvailableEvent(EventBase):
    """Dataclass for the `fiveg_core_gnb` available event."""

    def __init__(self, handle: Handle, tac: str, plmns: list[PLMNConfig]):
        """Set CU / gNodeB's TAC and PLMNs."""
        super().__init__(handle)
        self.tac = tac
        self.plmns = plmns

    def snapshot(self) -> dict:
        """Return event data."""
        return {
            "tac": self.tac,
            "plmns": self.plmns,
        }

    def restore(self, snapshot: dict) -> None:
        """Restore event data.

        Args:
            snapshot (dict): contains information to be restored.
        """
        self.tac = snapshot["tac"]
        self.plmns = snapshot["plmns"]


class FivegCoreGnbRequirerAppData(BaseModel):
    cu_ci: str = Field(
        description="CU/gNB unique identifier",
        examples=["gnb001"],
    )


class RequirerSchema(DataBagSchema):
    """Requirer schema for fiveg_core_gnb."""

    app_data: FivegCoreGnbRequirerAppData


def data_matches_requirer_schema(data: dict) -> bool:
    """Return whether data matches requirer schema.

    Args:
        data (dict): Data to be validated.

    Returns:
        bool: True if data matches requirer schema, False otherwise.
    """
    try:
        RequirerSchema(app_data=FivegCoreGnbRequirerAppData(**data))
        return True
    except ValidationError as e:
        logger.error("Invalid data: %s", e)
        return False


class FivegCoreGnbRequirerCharmEvents(CharmEvents):
    """Custom events for the FivegCoreGnbRequirer."""

    fiveg_core_gnb_available = EventSource(FivegCoreGnbAvailableEvent)


class FivegCoreGnbRequires(Object):
    """Class to be instantiated by requirer of the `fiveg_core_gnb`."""

    on = FivegCoreGnbRequirerCharmEvents()  # type: ignore

    def __init__(self, charm: CharmBase, relation_name: str, cu_id: str):
        """Observes relation joined and relation changed events.

        Args:
            charm: Juju charm
            relation_name (str): Relation name
        """
        self.relation_name = relation_name
        self.cu_id = cu_id
        self.charm = charm
        super().__init__(charm, relation_name)
        self.framework.observe(charm.on[relation_name].relation_joined, self._on_relation_changed)
        self.framework.observe(charm.on[relation_name].relation_changed, self._on_relation_changed)

    def publish_gnb_information(
            self, relation_id: int, cu_id: int
    ) -> None:
        """Set CU/gNB identifier in the relation data.

        Args:
            relation_id (str): Relation ID.
            cu_id (int): CU/gNB unique identifier.
        """
        if not data_matches_requirer_schema(
                data={"cu_id": cu_id}
        ):
            raise ValueError(f"Invalid fiveG core gNB data: {cu_id}")
        relation = self.model.get_relation(
            relation_name=self.relation_name, relation_id=relation_id
        )
        if not relation:
            raise RuntimeError(f"Relation {self.relation_name} not created yet.")
        relation.data[self.charm.app]["cu_id"] = str(cu_id)

    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """Triggered every time there's a change in relation data.

        Args:
            event (RelationChangedEvent): Juju event
        """
        relation_data = event.relation.data
        tac = relation_data[event.app].get("tac")
        plmns = relation_data[event.app].get("plmns")
        if tac and plmns:
            self.on.fiveg_core_gnb_available.emit(tac=tac, plmns=plmns)
