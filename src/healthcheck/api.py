from fastapi import APIRouter

router = APIRouter(tags=['Служебные'])


@router.get('/healthcheck', summary='Проверка работоспособности сервиса')
async def healthcheck() -> dict[str, str]:
    return {'status': 'ok'}
