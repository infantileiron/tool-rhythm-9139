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
    UNRECONCILED = 'unreconciled'


class Channel(StrEnum):
    MANUAL = 'manual'
    CABINET = 'cabinet'
    PAPER = 'paper'


class ReconState(StrEnum):
    CLEAN = 'clean'
    PARTIAL = 'partial'
    UNRECONCILED = 'unreconciled'
    NO_DATA = 'no_data'


class RecordState(StrEnum):
    MANUAL = 'manual'
    CONFIRMED = 'confirmed'
    PAIRED = 'paired'
    DISPUTED = 'disputed'
    STANDALONE = 'standalone'
    DUPLICATE = 'duplicate'
    AMBIGUOUS = 'ambiguous'
    UNMATCHED = 'unmatched'


BANDS = [(0, 8), (8, 11), (11, 14), (14, 17), (17, 20), (20, 24)]
ALGORITHM = 'cosine-dbscan-v2'
EXCEPTIONS = {StationStatus.NOISE, StationStatus.LOW, StationStatus.EMPTY, StationStatus.UNRECONCILED}

# 争议件数达到本站凭证量的一半时，实收基础已不足以代表该站节律，整站转为未对账。
DISPUTE_SHARE = 0.5
# 只有柜机流水或只有纸联、且站点与日期明确的记录，按单边实收计入。
MAX_IMPORT_ROWS = 10000


def band_index(hour):
    for index, (start, end) in enumerate(BANDS):
        if start <= hour < end:
            return index
    raise ValueError(f'小时超出时段边界: {hour}')
