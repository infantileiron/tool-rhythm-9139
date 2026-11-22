from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


Code = Annotated[str, StringConstraints(pattern=r'^[A-Z][A-Z0-9-]{1,11}$')]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=240)]


class Login(Input):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=128)


class StationInput(Input):
    code: Code
    name: str = Field(min_length=2, max_length=60)
    address: str = Field(min_length=2, max_length=100)
    steward: str = Field(min_length=2, max_length=40)


class RecordInput(Input):
    station_code: Code
    day: date
    hour: int = Field(ge=0, le=23)
    quantity: int = Field(ge=1, le=9999)
    source: str = Field(min_length=2, max_length=80)


class Correction(Input):
    quantity: int = Field(ge=1, le=9999)
    source: str = Field(min_length=2, max_length=80)
    revision: int = Field(ge=1)


class Period(Input):
    start: date
    end: date

    @model_validator(mode='after')
    def check_period(self):
        if not 0 <= (self.end - self.start).days < 93:
            raise ValueError('日期窗口须为连续 1–93 天，含起止日')
        return self


class PlanInput(Period):
    title: str = Field(min_length=2, max_length=80)
    eps: float = Field(ge=0, le=1)
    min_points: int = Field(ge=2, le=20)
    min_returns: int = Field(ge=1, le=9999)


class PublishInput(Input):
    memo: Note
    groups: dict[str, Note] = Field(max_length=250)
    exceptions: dict[Code, Note] = Field(max_length=250)
