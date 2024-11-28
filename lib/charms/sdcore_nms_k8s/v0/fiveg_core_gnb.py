# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Library for the `fiveg_core_gnb` relation.

This library contains the Requires and Provides classes for handling the `fiveg_core_gnb`
interface.

The purpose of this library is to provide a way for a 5G Core to provide network information and
configuration to CUs/gNodeBs.

To get started using the library, you need to fetch the library using `charmcraft`.

```shell
cd some-charm
charmcraft fetch-lib charms.sdcore_nms_k8s.v0.fiveg_core_gnb
```

Add the following libraries to the charm's `requirements.txt` file:
- pydantic
- pytest-interface-tester

Charms providing the `fiveg_core_gnb` relation should use `FivegCoreGnbProvides`.
The class `PLMNConfig` represents the configuration of a PLMN for the CU/gNodeB. It is composed by
the Mobile Country Code (MCC), the Mobile Network Code (MNC), the Slice Service Type (SST) and the
Slice Differentiator (SD). Each CU can be configured with a single Tracking Area Code (TAC) and
multiple PLMNS.

Typical usage of this class would look something like:

    ```python
    ...
    from charms.sdcore_gnbsim_k8s.v0.fiveg_core_gnb import FivegCoreGnbProvides, PLMNConfig
    ...

    class SomeProviderCharm(CharmBase):

        def __init__(self, *args):
            ...
            self.fiveg_core_gnb_provider = FivegCoreGnbProvides(
                charm=self,
                relation_name="fiveg_core_gnb"
                )
            ...
            self.framework.observe(
                self.fiveg_core_gnb_provider.on.gnb_available,
                self._on_gnb_available
            )

        def _on_gnb_available(self, event):
            ...
            # implement the logic to populate the list of PLMNs.
            plmns = [PLMNConfig(mcc=..., mnc=..., sst=..., sd=...)
            self.fiveg_core_gnb_provider.publish_fiveg_core_gnb_information(
                relation_id=event.relation_id,
                tac=tac,
                plmns=plmns,
            )
    ```

    And a corresponding section in charm's `charmcraft.yaml`:
    ```
    provides:
        fiveg_core_gnb:  # Relation name
            interface: fiveg_core_gnb  # Relation interface
    ```

Charms that require the `fiveg_core_gnb` relation should use `FivegCoreGnbRequires`.
Typical usage of this class would look something like:

    ```python
    ...
    from charms.sdcore_nms_k8s.v0.fiveg_core_gnb import FivegCoreGnbRequires
    ...

    class SomeRequirerCharm(CharmBase):

        CU_NAME = "gnb001"

        def __init__(self, *args):
            ...
            self.fiveg_core_gnb = FivegCoreGnbRequires(
                charm=self,
                relation_name="fiveg_core_gnb"
            )
            ...
            # on relation-joined the charm shall publish the CU/gNodeB name to the databag
            self.framework.observe(
                self.on.fiveg_core_gnb_relation_joined, self._on_fiveg_core_gnb_relation_joined
            )
            self.framework.observe(self.fiveg_core_gnb.on.gnb_config_available,
                self._on_gnb_config_available)

        def _on_fiveg_core_gnb_relation_joined(self, event: RelationJoinedEvent):
            relation_id = event.relation.id
            self.fiveg_core_gnb.publish_gnb_information(
                relation_id=relation_id,
                cu_name=self.CU_NAME,
            )

        def _on_gnb_config_available(self, event):
            tac = event.tac,
            plmns = event.plmns,
            # Do something with the TAC and PLMNs.
    ```

    And a corresponding section in charm's `charmcraft.yaml`:
    ```
    requires:
        fiveg_core_gnb:  # Relation name
            interface: fiveg_core_gnb  # Relation interface
    ```
"""
import json
import logging
from dataclasses import dataclass
from typing import Optional

from interface_tester.schema_base import DataBagSchema
from ops.charm import CharmBase
from ops.framework import Object
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
            "cu_name": "gnb001",
        }
"""


@dataclass
class PLMNConfig(BaseModel):
    """Dataclass representing the configuration for a PLMN."""

    def __init__(self, mcc: str, mnc: str, sst: int, sd: Optional[int] = None) -> None:
        super().__init__(mcc=mcc, mnc=mnc, sst=sst, sd=sd)

    mcc: str = Field(
        description="Mobile Country Code",
        examples=["001", "208", "302"],
        pattern=r"[0-9][0-9][0-9]",
    )
    mnc: str = Field(
        description="Mobile Network Code",
        examples=["01", "001", "999"],
        pattern=r"[0-9][0-9][0-9]?",
    )
    sst: int = Field(
        description="Slice/Service Type",
        strict=True,
        examples=[1, 2, 3, 4],
        ge=0,
        le=255,
    )
    sd: Optional[int] = Field(
        description="Slice Differentiator",
        strict=True,
        default=None,
        examples=[1],
        ge=0,
        le=16777215,
    )

    def asdict(self):
        """Convert the dataclass into a dictionary."""
        return {"mcc": self.mcc, "mnc": self.mnc, "sst": self.sst, "sd": self.sd}


class FivegCoreGnbProviderAppData(BaseModel):
    """Provider application data for fiveg_core_gnb."""
    tac: int = Field(
        description="Tracking Area Code",
        strict=True,
        examples=[1],
        ge=1,
        le=16777215,
    )
    plmns: list[PLMNConfig]


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


class FivegCoreGnbProvides(Object):
    """Class to be instantiated by provider of the `fiveg_core_gnb`."""

    def __init__(self, charm: CharmBase, relation_name: str):
        """Observe relation joined event.

        Args:
            charm: Juju charm
            relation_name (str): Relation name
        """
        self.relation_name = relation_name
        self.charm = charm
        super().__init__(charm, relation_name)

    def publish_gnb_config_information(
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
        relation.data[self.charm.app].update(
            {
                "tac": str(tac),
                "plmns": json.dumps([plmn.asdict() for plmn in plmns])
            }
        )


class FivegCoreGnbRequirerAppData(BaseModel):
    """Requirer application data for fiveg_core_gnb."""
    cu_name: str = Field(
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


class FivegCoreGnbRequires(Object):
    """Class to be instantiated by requirer of the `fiveg_core_gnb`."""

    def __init__(self, charm: CharmBase, relation_name: str):
        """Observes relation changed events.

        Args:
            charm: Juju charm
            relation_name (str): Relation name
        """
        self.relation_name = relation_name
        self.charm = charm
        super().__init__(charm, relation_name)

    def publish_gnb_information(
        self, relation_id: int, cu_name: str
    ) -> None:
        """Set CU/gNB identifier in the relation data.

        Args:
            relation_id (str): Relation ID.
            cu_name (str): CU/gNB unique identifier.
        """
        if not self.charm.unit.is_leader():
            raise RuntimeError("Unit must be leader to set application relation data.")

        if not data_matches_requirer_schema(
            data={"cu_name": cu_name}
        ):
            raise ValueError(f"Invalid fiveG core gNB data: {cu_name}")

        relation = self.model.get_relation(
            relation_name=self.relation_name, relation_id=relation_id
        )
        if not relation:
            raise RuntimeError(f"Relation {self.relation_name} not created yet.")

        if relation not in self.model.relations[self.relation_name]:
            raise RuntimeError(f"Relation {self.relation_name} not created yet.")

        relation.data[self.charm.app].update({"cu_name": cu_name})
