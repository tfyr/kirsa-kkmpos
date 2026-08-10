from settings_local import viki_port, viki_baudrate, viki_options
from vikiprint import VikiCM
from decimal import Decimal
import logging
from fastapi import HTTPException


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.FileHandler("py_log.log", encoding='utf-8', mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_shift_and_next_cheque_number():
    with VikiCM(viki_port, viki_baudrate) as viki:
        try:
            shift = viki.get_shift_number()
            cheque_number = viki.get_cheque_number()
            return shift, cheque_number
        except Exception as e:
            logger.error("Unexpected error in resolve_shift_and_next_cheque_number: %s", e)
            raise HTTPException(status_code=500, detail=f"Internal server error {e}")


def cheque(data, pay_type, beznal, cash, operation_type, tax_group_value, no_print, tax_rate_value):
    with VikiCM(viki_port, viki_baudrate) as viki:
        kkt_document_opened = False
        try:
            kkt_serial_number = viki.get_serial_number()
            viki.open_check(operation_type, tax_group_value, no_print)
            kkt_document_opened = True
            # shift = viki.get_shift_number()
            # cheque_number = viki.get_cheque_number()

            total = 0
            for i, pos in enumerate(data, 1):
                if Decimal(pos['amount']) > 0:
                    if operation_type == 0:
                        viki.income(round(Decimal(pos['amount']), 3), round(Decimal(pos['price']), 2), pos['name'],
                                    tax_rate_value, None)
                    elif operation_type == 1:
                        viki.refund(round(Decimal(pos['amount']), 3), round(Decimal(pos['price']), 2), pos['name'],
                                    tax_rate_value, None)
                    else:
                        raise Exception('unknown operation type')
                    total += round(Decimal(pos['amount']), 3) * round(Decimal(pos['price']), 2)
            if beznal is not None or cash is not None:
                if beznal:
                    viki.payment(1, round(beznal, 2), None)
                if cash:
                    viki.payment(0, round(cash, 2), None)
            else:
                viki.payment(1 if pay_type else 0, round(total, 2), None)
            cc = viki.close_check()
            return kkt_serial_number, cc['shift'], cc['chequeNumber'], cc['fd'], cc['fp']
        except Exception as e:
            logger.error(e)
            if kkt_document_opened:
                try:
                    viki.cancel_check()
                except Exception as e:
                    logger.error("Unexpected error in while viki.cancel_check call: %s", e)
            logger.error("Unexpected error in cheque: %s", e)
            raise Exception(f"status_code=500, Internal server error {e}") # HTTPException(status_code=500, detail=f"Internal server error {e}")
