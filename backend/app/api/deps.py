from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings
from app.keitaro.client import KeitaroClient
from app.services.catalog import Catalog
from app.services.editor import Editor


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_keitaro(request: Request) -> KeitaroClient:
    return request.app.state.keitaro


def get_catalog(request: Request) -> Catalog:
    return request.app.state.catalog


def get_editor(request: Request) -> Editor:
    return request.app.state.editor


SettingsDep = Annotated[Settings, Depends(get_settings)]
KeitaroDep = Annotated[KeitaroClient, Depends(get_keitaro)]
CatalogDep = Annotated[Catalog, Depends(get_catalog)]
EditorDep = Annotated[Editor, Depends(get_editor)]
