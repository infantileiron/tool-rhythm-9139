from enum import StrEnum


class Role(StrEnum):
    ADMIN = 'admin'
    ANALYST = 'analyst'
    OBSERVER = 'observer'


class RunStatus(StrEnum):
    QUEUED = 'queued'
    RUNNING = 'running'
    READY = 'ready'
    PUBLISHED = 'published'
    FAILED = 'failed'


class StationStatus(StrEnum):
    CORE = 'core'
    BORDER = 'border'
    NOISE = 'noise'
    LOW = 'low_sample'
    EMPTY = 'no_data'


BANDS = [(0, 8), (8, 11), (11, 14), (14, 17), (17, 20), (20, 24)]
ALGORITHM = 'cosine-dbscan-v1'
EXCEPTIONS = {StationStatus.NOISE, StationStatus.LOW, StationStatus.EMPTY}
