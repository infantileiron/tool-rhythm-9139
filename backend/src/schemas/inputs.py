from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


Code = Annotated[str, StringConstraints(pattern=r'^[A-Z][A-Z0-9-]{1,11}$')]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=240)]
ChannelName = Annotated[str, StringConstraints(pattern=r'^(cabinet|paper)$')]


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
    """校正记录。只有来源联单缺站点或日期时才允许补齐；其余字段可单独更新。"""

    quantity: int | None = Field(default=None, ge=1, le=9999)
    source: str | None = Field(default=None, min_length=2, max_length=80)
    revision: int = Field(ge=1)
    station_code: Code | None = None
    day: date | None = None
    hour: int | None = Field(default=None, ge=0, le=23)


class Period(Input):
    start: date
    end: date

    @model_validator(mode='after')
    def check_period(self):
        if not 0 <= (self.end - self.start).days < 93:
            raise ValueError('日期窗口须为连续 1–93 天，含起止日')
        return self


class RecordQuery(Period):
    station_code: Code | None = None
    channel: Literal['manual', 'cabinet', 'paper'] | None = None


class ImportInput(Period):
    """一路归还联的文本导入。柜机流水必须带站点和日期；纸联可整批给默认站点/日期。"""

    channel: ChannelName
    filename: str = Field(min_length=2, max_length=120)
    content: str = Field(min_length=1)
    default_station: Code | None = None
    default_day: date | None = None

    @model_validator(mode='after')
    def check_defaults(self):
        if self.default_day and not self.start <= self.default_day <= self.end:
            raise ValueError('默认日期须在导入窗口内')
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
