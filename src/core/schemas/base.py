from pydantic import BaseModel, ConfigDict


class BaseFromAttrsModel(BaseModel):
    """Базовая модель для DTO, которые собираются из ORM-объектов"""

    model_config = ConfigDict(from_attributes=True, frozen=True)
