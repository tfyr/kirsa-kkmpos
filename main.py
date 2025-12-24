import json
import logging
import argparse
from decimal import Decimal

from pydantic import BaseModel

from vikiprint import VikiCM

from fastapi import FastAPI, HTTPException, Request
import uvicorn

from settings_local import viki_port, viki_baudrate, viki_options

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


class ChequeParams(BaseModel):
    operation_type: int
    tax_group_value: int
    tax_rate_value: int
    no_print: bool
    beznal: str
    cash: str
    pay_type: int | None = None
    data: str

@app.post("/kirsa-kkmpos/cheque")
def resolve_cheque(p: ChequeParams):
    with VikiCM(viki_port, viki_baudrate) as viki:
        kkt_document_opened = False
        try:
            try:
                data = json.loads(p.data)
                beznal = Decimal(json.loads(p.beznal))
                cash = Decimal(json.loads(p.cash))
                viki.open_check(p.operation_type, p.tax_group_value, p.no_print)
                kkt_document_opened = True
                shift = viki.get_shift_number()
                cheque_number = viki.get_cheque_number()

                total = 0
                for i, pos in enumerate(data, 1):
                    if Decimal(pos['amount']) > 0:
                        if p.operation_type == 0:
                            viki.income(round(Decimal(pos['amount']), 3), round(Decimal(pos['price']), 2), pos['name'],
                                        p.tax_rate_value, None)
                        elif p.operation_type == 1:
                            viki.refund(round(Decimal(pos['amount']), 3), round(Decimal(pos['price']), 2), pos['name'],
                                        p.tax_rate_value, None)
                        else:
                            raise Exception('unknown operation type')
                        total += round(Decimal(pos['amount']), 3) * round(Decimal(pos['price']), 2)
                if beznal is not None or cash is not None:
                    if beznal:
                        viki.payment(1, round(beznal, 2), None)
                    if cash:
                        viki.payment(0, round(cash, 2), None)
                else:
                    viki.payment(1 if p.pay_type else 0, round(total, 2), None)
                viki.close_check()
            except Exception as e:
                if kkt_document_opened:
                    viki.cancel_check()
                    raise e
            #viki.cancel_check()
            return shift, cheque_number
        except Exception as e:
            logger.error("Unexpected error in resolve_cancel_cheque: %s", e)
            raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/kirsa-kkmpos/shift_and_next_cheque_number")
def resolve_shift_and_next_cheque_number():
    with VikiCM(viki_port, viki_baudrate) as viki:
        kkt_document_opened = False
        try:
            shift = viki.get_shift_number()
            cheque_number = viki.get_cheque_number()
            return shift, cheque_number
        except Exception as e:
            logger.error("Unexpected error in resolve_shift_and_next_cheque_number: %s", e)
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
            cash_counter['chequeNumber'] = viki.get_cheque_number()
            cash_counter['cashTotalX'] = viki.get_cash_total_x()
            cash_counter['getShiftOpeningDateTime'] = str(viki.get_shift_opening_date_time()['date'])
            fudt = viki.get_first_unsended()['firstUnsendedDatetime']
            cash_counter['firstUnsendedDatetime']  = str(fudt) if fudt else None
            cash_counter['getFnExpiryDate'] = str(viki.get_fn_expiry_date()['expiryDate'])
            return cash_counter
    except Exception as e:
        logger.error("Unexpected error in get_kkm_counters: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal server error {e}")


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