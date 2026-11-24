from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings
from app.keitaro.client import KeitaroClient
from app.services.catalog import Catalog


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_keitaro(request: Request) -> KeitaroClient:
    return request.app.state.keitaro


def get_catalog(request: Request) -> Catalog:
    return request.app.state.catalog


SettingsDep = Annotated[Settings, Depends(get_settings)]
KeitaroDep = Annotated[KeitaroClient, Depends(get_keitaro)]
CatalogDep = Annotated[Catalog, Depends(get_catalog)]
