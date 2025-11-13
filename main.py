import logging
import argparse

from fastapi import FastAPI, HTTPException, Request
import uvicorn

from settings_local import viki_port, viki_baudrate, viki_options

from vikiprint import VikiCM

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.FileHandler("py_log.log", encoding='utf-8', mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="KIRSA KKM POS Service",
    description="Микросервис для работы с кассами KIRSA",
    version="1.0.0",
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware для логирования запросов"""
    logger.info(
        f"Request: {request.method} {request.url} - Client: {request.client.host if request.client else 'Unknown'}"
    )

    try:
        response = await call_next(request)
        logger.info(f"Response: {response.status_code} for {request.method} {request.url}")
        return response
    except Exception as e:
        logger.error(f"Error processing request {request.method} {request.url}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/kirsa-kkmpos/close_shift")
def resolve_close_shift():
    try:
        with VikiCM(viki_port, viki_baudrate) as viki:
            viki.close_shift("Иванова")
    except Exception as e:
        logger.error("Unexpected error in resolve_close_shift: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/kirsa-kkmpos/cancel_cheque")
def resolve_cancel_cheque():
    with VikiCM(viki_port, viki_baudrate) as viki:
        try:
            viki.cancel_check()
        except Exception as e:
            logger.error("Unexpected error in resolve_cancel_cheque: %s", e)
            raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/kirsa-kkmpos/open_shift")
def resolve_open_shift():
    try:
        with VikiCM(viki_port, viki_baudrate) as viki:
            viki.open_shift('Иванова')
    except Exception as e:
        logger.error("Unexpected error in resolve_open_shift: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/kirsa-kkmpos/get_kkm_status")
def resolve_get_kkm_status(auto_start_work_if_need=True):
    try:
        with VikiCM(viki_port, viki_baudrate, viki_options) as viki:
            ret = viki.get_kkm_status()
            current_flags = ret['currentFlags']
            if current_flags& 0b01 and auto_start_work_if_need:  # no started work
                viki.start_work()
            return ret
    except Exception as e:
        logger.error("Unexpected error in get_kkm_status: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal server error {e}")


@app.get("/kirsa-kkmpos/get_kkm_counters")
def resolve_get_kkm_counters():
    try:
        with VikiCM(viki_port, viki_baudrate, viki_options) as viki:
            cash_counter = viki.get_cash_counters()
            cash_counter['serialNumber'] = viki.get_serial_number()
            cash_counter['shiftNumber'] = viki.get_shift_number()
            cash_counter['cashTotalX'] = viki.get_cash_total_x()
            cash_counter['getShiftOpeningDateTime'] = str(viki.get_shift_opening_date_time()['date'])

            cash_counter['firstUnsendedDatetime']  = str(viki.get_first_unsended()['firstUnsendedDatetime'])
            cash_counter['getFnExpiryDate'] = str(viki.get_fn_expiry_date()['expiryDate'])
            return cash_counter
    except Exception as e:
        logger.error("Unexpected error in get_kkm_counters: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--uds', help='use sock')
    parser.add_argument('--host', default='127.0.0.1', help='host address')
    parser.add_argument('--port', default=8001, type=int, help='port number')
    parser.add_argument('--workers', default=1, type=int, help='Number of workers')
    args = parser.parse_args()

    config = {
        "app": "main:app",
        "reload": False,
        "log_level": "info",
        "workers": args.workers,
    }

    if args.uds:
        config["uds"] = args.uds
        logger.info("Starting server on Unix socket: %s", args.uds)
    else:
        config["host"] = args.host
        config["port"] = args.port
        logger.info("Starting server on %s:%s", args.host, args.port)

    uvicorn.run(**config)