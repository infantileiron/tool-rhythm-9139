from fastapi import APIRouter, Depends, Query, Response

from src.constants.domain import Role
from src.controllers import session
from src.middlewares.auth import current, only
from src.schemas.inputs import Code, Correction, Login, Period, PlanInput, PublishInput, RecordInput, StationInput
from src.services import intake, plans

router = APIRouter()
analyst = only(Role.ANALYST)
admin = only(Role.ADMIN)


@router.post('/login')
def login(data: Login):
    return session.login(data)


@router.get('/me')
def whoami(viewer=Depends(current)):
    return {'username': viewer['sub'], 'name': viewer['name'], 'role': viewer['role']}


@router.get('/stations')
def station_list(viewer=Depends(current)):
    return intake.station_list()


@router.post('/stations', status_code=201)
def station_create(data: StationInput, viewer=Depends(analyst)):
    return intake.create_station(data, viewer['sub'])


@router.post('/records/search')
def record_list(period: Period, station_code: Code | None = None,
                page: int = Query(1, ge=1, le=1000000), viewer=Depends(current)):
    return intake.records(period, station_code, page)


@router.post('/records', status_code=201)
def record_create(data: RecordInput, viewer=Depends(analyst)):
    return intake.create_record(data, viewer['sub'])


@router.patch('/records/{record_id}')
def record_correct(record_id: int, data: Correction, viewer=Depends(analyst)):
    return intake.correct_record(record_id, data, viewer['sub'])


@router.get('/runs')
def run_list(viewer=Depends(current)):
    return plans.summaries(viewer)


@router.post('/runs', status_code=202)
def run_queue(data: PlanInput, viewer=Depends(analyst)):
    return plans.queue_run(data, viewer['sub'])


@router.get('/runs/{run_id}')
def run_details(run_id: int, viewer=Depends(current)):
    return plans.details(run_id, viewer)


@router.post('/runs/{run_id}/publish')
def run_publish(run_id: int, data: PublishInput, viewer=Depends(admin)):
    return plans.publish(run_id, data, viewer['sub'])


@router.get('/runs/{run_id}/duty.csv')
def duty_export(run_id: int, viewer=Depends(current)):
    return Response(plans.export_csv(plans.details(run_id, viewer)), media_type='text/csv',
                    headers={'Content-Disposition': f'attachment; filename="duty-v{run_id}.csv"'})
