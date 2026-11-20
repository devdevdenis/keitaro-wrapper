from app.keitaro import KeitaroAPI, KeitaroAPIError
from app.services.errors import ServiceError


async def ensure_offer_available(keitaro: KeitaroAPI, offer_id: int) -> None:
    """Оффер должен существовать в Keitaro и не быть в архиве."""
    try:
        offer = await keitaro.get_offer(offer_id)
    except KeitaroAPIError as exc:
        if exc.status_code == 404:
            raise ServiceError(f"Оффер #{offer_id} не найден в Keitaro", status_code=422) from exc
        raise
    if offer.get("state") == "deleted":
        raise ServiceError(f"Оффер #{offer_id} в архиве Keitaro", status_code=422)
