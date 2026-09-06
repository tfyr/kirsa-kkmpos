from settings_local import kkt_port, kkt_baudrate, viki_options
from shtrikh import ShtrikhCM
from vikiprint import VikiCM
from decimal import Decimal
import logging

viki_or_shrikh = 0

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
    with VikiCM(kkt_port, kkt_baudrate) as viki:
        try:
            shift = viki.get_shift_number()
            cheque_number = viki.get_cheque_number()
            return shift, cheque_number
        except Exception as e:
            logger.error("Unexpected error in resolve_shift_and_next_cheque_number: %s", e)
            raise Exception(f"Internal server error {e}")


def cheque(data, pay_type, ecash, cash, operation_type, tax_group_value, no_print, tax_rate_value):
    kkt_document_opened = False
    kkt_document_closed = False
    with VikiCM(kkt_port, kkt_baudrate) if viki_or_shrikh else ShtrikhCM(kkt_port, kkt_baudrate) as kkt_cm:
        try:
            kkt_serial_number = kkt_cm.get_serial_number()
            if operation_type==0:
                open_check_operation_type = 0
            elif operation_type == 1:
                open_check_operation_type = 2
            else:
                raise Exception(f'unhandling operation type {operation_type}')
            kkt_cm.open_check(open_check_operation_type, tax_group_value, no_print)
            kkt_document_opened = True
            # shift = viki.get_shift_number()
            # cheque_number = viki.get_cheque_number()

            total = 0
            for i, pos in enumerate(data, 1):
                if Decimal(pos['amount']) > 0:
                    if operation_type == 0:
                        kkt_cm.income(round(Decimal(pos['amount']), 3), round(Decimal(pos['price']), 2), pos['name'],
                                    tax_rate_value, None)
                    elif operation_type == 1:
                        kkt_cm.refund(round(Decimal(pos['amount']), 3), round(Decimal(pos['price']), 2), pos['name'],
                                    tax_rate_value, None)
                    else:
                        raise Exception('unknown operation type')
                    total += round(Decimal(pos['amount']), 3) * round(Decimal(pos['price']), 2)
            if ecash is not None or cash is not None:
                if ecash:
                    kkt_cm.payment(1, round(ecash, 2), None)
                if cash:
                    kkt_cm.payment(0, round(cash, 2), None)
            else:
                kkt_cm.payment(1 if pay_type else 0, round(total, 2), None)
            cc = kkt_cm.close_check(cash, ecash, tax_group_value)
            kkt_document_closed=True
            return kkt_serial_number, cc['shift'], cc['chequeNumber'], cc['fd'], cc['fp']
        except Exception as e1:
            logger.error(e1)
            if kkt_document_opened and not kkt_document_closed:
                try:
                    kkt_cm.cancel_check()
                except Exception as e:
                    logger.error("Unexpected error in while viki.cancel_check call: %s", e)
            logger.error("Unexpected error in cheque: %s", e1)
            raise Exception(f"status_code=500, Internal server error {e1}") # HTTPException(status_code=500, detail=f"Internal server error {e}")
